"""Sync power and training plan data from Stryd PowerCenter.

Primary method: Stryd calendar API (fast, reliable).
Fallback: Playwright browser scraping (for when token is unavailable).

To set up:
1. Add STRYD_TOKEN, STRYD_USER_ID to .env
2. (Optional fallback) pip install playwright && playwright install chromium
3. (Optional fallback) Add STRYD_EMAIL, STRYD_PASSWORD to .env
"""
import argparse
import os
import re
from datetime import date, datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

from sync.csv_utils import append_rows

STRYD_CALENDAR_URL = "https://www.stryd.com/powercenter/athletes/{user_id}/calendar"


# --- Duration / distance / power parsers (pure functions, no browser) ---


def _parse_duration_to_minutes(duration_str: str) -> float | None:
    """Parse duration string like '1:00:00' or '45:00' to minutes."""
    parts = duration_str.strip().split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 60 + int(parts[1]) + int(parts[2]) / 60
        elif len(parts) == 2:
            return int(parts[0]) + int(parts[1]) / 60
    except ValueError:
        return None
    return None


def _parse_duration_to_seconds(duration_str: str) -> int | None:
    """Parse duration string like '1:00:01' or '30:22' to seconds."""
    parts = duration_str.strip().split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
    except ValueError:
        return None
    return None


def _parse_distance_km(text: str) -> float | None:
    """Parse distance string like '11.38km' or '11.22 km' to float."""
    m = re.match(r"([\d.]+)\s*km", text)
    return float(m.group(1)) if m else None


def _parse_power_range(text: str) -> tuple[int | None, int | None]:
    """Parse power target string like '206 - 231 W' to (low, high).

    Handles regular hyphens, en-dashes, and em-dashes.
    """
    m = re.search(r"(\d+)\s*[-–—]\s*(\d+)\s*W", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def _parse_stat_value(text: str) -> str:
    """Extract numeric value from stat text like '220 W' or '9.5 kN/m'."""
    m = re.match(r"([\d.]+)", text.strip())
    return m.group(1) if m else ""


def _workout_type_from_name(name: str) -> str:
    """Extract workout type from Stryd plan name like 'Day 46 - Steady Aerobic'."""
    m = re.match(r"Day\s+\d+\s*-\s*(.+)", name)
    return m.group(1).strip().lower() if m else name.lower()


# --- Calendar card parsers ---


def parse_calendar_button_text(button_text: str) -> dict | None:
    """Parse a Stryd calendar workout button's accessible text.

    Handles both formats:
    - aria-label: 'stryd Day 46 - Steady Aerobic 1:00:00 11.38km 52RSS'
    - inner_text with newlines: 'Day 46 - Steady Aerobic\n1:00:00\n11.38km\n52RSS'
    Distance and RSS may be absent for time-based workouts.
    Returns a dict with workout fields, or None if unparseable.
    """
    # Normalize: strip "stryd" prefix, replace newlines with spaces
    text = button_text.strip()
    if text.lower().startswith("stryd"):
        text = text[5:].strip()
    text = re.sub(r"\s+", " ", text)

    # Try full pattern first (name + duration + distance + RSS)
    m = re.match(
        r"(Day\s+\d+\s*-\s*.+?)\s+"  # workout name
        r"(\d+:\d+(?::\d+)?)\s+"      # duration
        r"([\d.]+\s*km)\s+"           # distance
        r"(\d+\s*RSS)",               # RSS
        text,
    )
    if m:
        return {
            "workout_name": m.group(1),
            "workout_type": _workout_type_from_name(m.group(1)),
            "duration_minutes": _parse_duration_to_minutes(m.group(2)),
            "distance_km": _parse_distance_km(m.group(3)),
        }

    # Fallback: extract individual fields from text that contains "Day N - Name"
    # Name is letters/spaces only, stops before digits (duration/distance)
    name_m = re.search(r"(Day\s+\d+\s*-\s*[A-Za-z][A-Za-z ]*[A-Za-z])", text)
    if not name_m:
        return None

    result = {
        "workout_name": name_m.group(1),
        "workout_type": _workout_type_from_name(name_m.group(1)),
        "duration_minutes": None,
        "distance_km": None,
    }

    # Duration: H:MM:SS or MM:SS pattern
    dur_m = re.search(r"\b(\d+:\d{2}(?::\d{2})?)\b", text)
    if dur_m:
        result["duration_minutes"] = _parse_duration_to_minutes(dur_m.group(1))

    # Distance: N.NNkm
    dist_m = re.search(r"([\d.]+)\s*km", text)
    if dist_m:
        result["distance_km"] = float(dist_m.group(1))

    return result


def parse_activity_detail(stats: dict[str, str]) -> dict:
    """Transform scraped activity detail stats into our power_data.csv schema.

    Input keys match the label text from the detail view:
    date_str, start_time_str, moving_time, distance, power, form_power,
    gct, lss, rss, cp.
    """
    duration_sec = _parse_duration_to_seconds(stats.get("moving_time", ""))
    distance_km = _parse_distance_km(stats.get("distance", ""))
    return {
        "date": stats.get("date_str", ""),
        "start_time": stats.get("start_time_str", ""),
        "avg_power": _parse_stat_value(stats.get("power", "")),
        "max_power": "",  # not available in detail view
        "form_power": _parse_stat_value(stats.get("form_power", "")),
        "leg_spring_stiffness": _parse_stat_value(stats.get("lss", "")),
        "ground_time_ms": _parse_stat_value(stats.get("gct", "")),
        "rss": _parse_stat_value(stats.get("rss", "")),
        "cp_estimate": _parse_stat_value(stats.get("cp", "")),
        "distance_km": str(distance_km) if distance_km is not None else "",
        "duration_sec": str(duration_sec) if duration_sec is not None else "",
    }


def parse_training_plan(raw_workouts: list[dict]) -> list[dict]:
    """Transform Stryd training plan data into our CSV schema."""
    rows = []
    for w in raw_workouts:
        rows.append({
            "date": w.get("date", ""),
            "workout_type": w.get("workout_type", ""),
            "planned_duration_min": str(w["duration_minutes"]) if w.get("duration_minutes") is not None else "",
            "planned_distance_km": str(w["distance_km"]) if w.get("distance_km") is not None else "",
            "target_power_min": str(w["power_target_low"]) if w.get("power_target_low") is not None else "",
            "target_power_max": str(w["power_target_high"]) if w.get("power_target_high") is not None else "",
            "workout_description": w.get("workout_description", ""),
        })
    return rows


# --- Browser helpers ---


def _login_with_credentials(page, email: str, password: str, calendar_url: str) -> None:
    """Log into Stryd via the sign-in form and navigate to the calendar."""
    page.goto(calendar_url)

    # Wait for either the login form (password field) or the calendar (h3 heading)
    page.wait_for_selector("input[type='password'], h3", timeout=30000)

    # If a password field is present, we need to log in
    password_field = page.query_selector("input[type='password']")
    if not password_field:
        return
    page.get_by_role("textbox", name="Email Address").fill(email)
    page.get_by_role("textbox", name="Password").fill(password)
    page.get_by_role("button", name="Continue", exact=True).click()
    page.wait_for_url("**/calendar**", timeout=30000)


def _login_with_token(page, token: str, calendar_url: str) -> None:
    """Inject a bearer token into localStorage and navigate to the calendar."""
    page.goto("https://www.stryd.com/powercenter")
    page.evaluate(f"() => {{ localStorage.setItem('token', '{token}'); }}")
    page.goto(calendar_url)


def _acquire_token_via_browser(email: str, password: str) -> str:
    """Log into Stryd via Playwright and extract the JWT from localStorage.

    This is a lightweight browser session — just login, grab token, close.
    The token can then be used for fast API calls without further scraping.
    """
    from playwright.sync_api import sync_playwright

    print("  Acquiring Stryd token via browser login...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        _login_with_credentials(
            page, email, password,
            STRYD_CALENDAR_URL.format(user_id="me"),
        )

        # Wait for the app to store the token after login
        page.wait_for_timeout(2000)
        token = page.evaluate("() => localStorage.getItem('token')")

        browser.close()

    if not token:
        raise RuntimeError("Login succeeded but no token found in localStorage")

    print("  Token acquired successfully")
    return token


def _get_calendar_month_year(page) -> tuple[int, int]:
    """Read the displayed month/year from the calendar heading (e.g. 'March 2026')."""
    heading = page.query_selector("h3")
    heading_text = heading.inner_text() if heading else ""
    try:
        dt = datetime.strptime(heading_text.strip(), "%B %Y")
        return dt.year, dt.month
    except ValueError:
        today = date.today()
        return today.year, today.month


def _resolve_cell_date(day_el, current_year: int, current_month: int) -> str | None:
    """Determine YYYY-MM-DD from a calendar cell's day paragraph element."""
    day_text = day_el.inner_text().strip()

    month = current_month
    year = current_year
    if "\n" in day_text or len(day_text) > 2:
        parts = day_text.split("\n") if "\n" in day_text else day_text.split()
        if len(parts) == 2:
            try:
                month = datetime.strptime(parts[0].strip(), "%b").month
                day_text = parts[1].strip()
                if month < current_month:
                    year += 1
            except ValueError:
                pass

    try:
        day_num = int(day_text)
    except ValueError:
        return None

    return f"{year}-{month:02d}-{day_num:02d}"


def _find_scroll_container_js() -> str:
    """Return JS snippet that finds the calendar's scrollable container."""
    return """
        const candidates = document.querySelectorAll('div');
        let scrollContainer = null;
        for (const div of candidates) {
            const style = window.getComputedStyle(div);
            if ((style.overflowY === 'auto' || style.overflowY === 'scroll')
                && div.scrollHeight > div.clientHeight
                && div.clientHeight > 200) {
                if (!scrollContainer || div.scrollHeight > scrollContainer.scrollHeight) {
                    scrollContainer = div;
                }
            }
        }
    """


def _scroll_calendar_to_top(page) -> None:
    """Scroll the calendar container upward repeatedly to trigger lazy-loading
    of earlier weeks, until no more content appears above.

    The Stryd calendar defaults to showing the current week and lazy-loads
    earlier weeks only when the user scrolls up. A single scrollTop=0 won't
    work if those weeks aren't in the DOM yet. We loop: scroll to top, wait
    for new content, repeat until scrollHeight stabilizes.
    """
    attempts = 0
    for attempt in range(15):
        prev_info = page.evaluate("""() => {
            %s
            if (!scrollContainer) return null;
            const before = scrollContainer.scrollHeight;
            scrollContainer.scrollTop = 0;
            return { scrollHeight: before };
        }""" % _find_scroll_container_js())

        if prev_info is None:
            # No scrollable container found — use keyboard fallback
            for _ in range(10):
                page.keyboard.press("Home")
            page.wait_for_timeout(1000)
            attempts = attempt + 1
            break

        page.wait_for_timeout(1500)

        new_height = page.evaluate("""() => {
            %s
            return scrollContainer ? scrollContainer.scrollHeight : 0;
        }""" % _find_scroll_container_js())

        attempts = attempt + 1
        if new_height <= prev_info["scrollHeight"]:
            break  # No new content loaded — all weeks are in the DOM

        print(f"    Scroll attempt {attempts}: new content loaded "
              f"({prev_info['scrollHeight']} -> {new_height})")

    print(f"    Scrolled calendar to top ({attempts} iteration(s))")


def _navigate_calendar_to_month(page, target_year: int, target_month: int) -> None:
    """Click the back arrow until the calendar shows the target month."""
    for _ in range(12):  # max 12 months back
        year, month = _get_calendar_month_year(page)
        if year == target_year and month == target_month:
            return
        # Click previous month button (left arrow, first nav button after Today)
        prev_btn = page.query_selector("button:has(img) + button:has(img)")
        if not prev_btn:
            # Fallback: find by position — it's the button right after "Today"
            buttons = page.query_selector_all("button")
            for i, btn in enumerate(buttons):
                if btn.inner_text().strip() == "Today" and i + 1 < len(buttons):
                    prev_btn = buttons[i + 1]
                    break
        if prev_btn:
            prev_btn.click()
            page.wait_for_timeout(1000)
        else:
            break


# --- Scraper functions ---


def _scrape_activity_detail(page) -> dict[str, str]:
    """Extract stats from an open activity detail view. Returns raw stat strings."""
    # Use JavaScript to extract all text from the page in a structured way
    raw = page.evaluate("""() => {
        const stats = {};

        // All paragraph elements — look for date header, summary stats, and metric pairs
        const paragraphs = document.querySelectorAll('p');
        const pTexts = Array.from(paragraphs).map(p => p.innerText.trim());

        // Date/time header: "March 18, 2026 at 04:21 PM"
        for (const t of pTexts) {
            const m = t.match(/^(\\w+ \\d+, \\d{4}) at (\\d+:\\d+ [AP]M)$/);
            if (m) {
                stats.date_header = t;
                break;
            }
        }

        // Summary stats: find label then next sibling value
        for (let i = 0; i < pTexts.length; i++) {
            if (pTexts[i] === 'MOVING TIME' && i + 1 < pTexts.length)
                stats.moving_time = pTexts[i + 1];
            if (pTexts[i] === 'DISTANCE' && i + 1 < pTexts.length)
                stats.distance = pTexts[i + 1];
            if (pTexts[i] === 'STRESS' && i + 1 < pTexts.length)
                stats.rss = pTexts[i + 1];
        }

        // Metric pairs: elements with exactly 2 <p> children (label + value)
        const allDivs = document.querySelectorAll('div');
        for (const div of allDivs) {
            const ps = div.querySelectorAll(':scope > p');
            if (ps.length === 2) {
                const label = ps[0].innerText.trim().toLowerCase();
                const value = ps[1].innerText.trim();
                if (['power', 'form power', 'gct', 'lss'].includes(label)) {
                    stats[label.replace(' ', '_')] = value;
                }
            }
        }

        // CP from chart: look for text matching "CP NNN W"
        const allText = document.body.innerText;
        const cpMatch = allText.match(/CP (\\d+) W/);
        if (cpMatch) stats.cp = cpMatch[1];

        return stats;
    }""")

    stats = {}

    # Parse date header
    if raw.get("date_header"):
        m = re.match(r"(\w+ \d+, \d{4}) at (\d+:\d+ [AP]M)", raw["date_header"])
        if m:
            try:
                dt = datetime.strptime(f"{m.group(1)} {m.group(2)}", "%B %d, %Y %I:%M %p")
                stats["date_str"] = dt.strftime("%Y-%m-%d")
                stats["start_time_str"] = dt.strftime("%Y-%m-%dT%H:%M:%S")
            except ValueError:
                pass

    if raw.get("moving_time"):
        stats["moving_time"] = raw["moving_time"]
    if raw.get("distance"):
        stats["distance"] = raw["distance"]
    if raw.get("rss"):
        stats["rss"] = raw["rss"].replace("RSS", "").strip()
    if raw.get("power"):
        stats["power"] = raw["power"]
    if raw.get("form_power"):
        stats["form_power"] = raw["form_power"]
    if raw.get("gct"):
        stats["gct"] = raw["gct"]
    if raw.get("lss"):
        stats["lss"] = raw["lss"]
    if raw.get("cp"):
        stats["cp"] = raw["cp"]

    return stats


def _parse_structured_intervals(modal_text: str) -> tuple[str, int | None, int | None]:
    """Parse structured workout intervals from modal text.

    Returns (workout_description, main_power_low, main_power_high).
    The main power range is from the highest-intensity split (the "main set").
    """
    # Split into sections by known headings: Warmup, Run, Recover, Cooldown, Splits
    # Pattern: heading lines followed by split rows with duration + power
    sections = []
    current_section = None

    for line in modal_text.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Detect section headings (e.g. "Warmup:", "Run/Recover:", "Cooldown:", "Splits:")
        heading_m = re.match(r"^(Warmup|Cooldown|Run(?:/Recover)?|Recover|Splits)\s*:?\s*$", line, re.IGNORECASE)
        if heading_m:
            current_section = {"name": heading_m.group(1), "splits": []}
            sections.append(current_section)
            continue

        # Detect split rows with duration and power target
        # e.g. "S:1  4:59  | Target: 189 - 216 W" or "S:1 1:00:00 Run | 206 - 231 W | 76 - 85%"
        # or "x2  20:00 | Target: 251 - 262 W"
        split_m = re.search(r"(?:S:\d+|x(\d+))?\s*(\d+:\d{2}(?::\d{2})?)\s*(?:\w+\s*)?\|?\s*(?:Target:\s*)?(\d+\s*[-–—]\s*\d+\s*W)", line)
        if split_m and current_section is not None:
            repeat = int(split_m.group(1)) if split_m.group(1) else 1
            duration_str = split_m.group(2)
            power_str = split_m.group(3)
            duration_min = _parse_duration_to_minutes(duration_str)
            p_low, p_high = _parse_power_range(power_str)
            current_section["splits"].append({
                "repeat": repeat,
                "duration_min": duration_min,
                "power_low": p_low,
                "power_high": p_high,
            })
            continue

        # Also try lines with just duration + power (no S: prefix)
        simple_m = re.search(r"(\d+:\d{2}(?::\d{2})?)\s*\|?\s*(?:Target:\s*)?(\d+\s*[-–—]\s*\d+\s*W)", line)
        if simple_m and current_section is not None:
            duration_str = simple_m.group(1)
            power_str = simple_m.group(2)
            duration_min = _parse_duration_to_minutes(duration_str)
            p_low, p_high = _parse_power_range(power_str)
            current_section["splits"].append({
                "repeat": 1,
                "duration_min": duration_min,
                "power_low": p_low,
                "power_high": p_high,
            })

    if not sections:
        # No structured sections found — try to get a single power range from the text
        m = re.search(r"(\d+)\s*[-–—]\s*(\d+)\s*W", modal_text)
        if m:
            return "", int(m.group(1)), int(m.group(2))
        return "", None, None

    # Build description string and find main set power
    desc_parts = []
    main_power_low = None
    main_power_high = None
    max_power = 0

    for section in sections:
        if section["name"].lower() == "splits":
            # Simple splits table (non-structured) — just use the first power range
            if section["splits"] and main_power_low is None:
                s = section["splits"][0]
                main_power_low = s["power_low"]
                main_power_high = s["power_high"]
            continue

        split_descs = []
        for s in section["splits"]:
            dur = f"{int(s['duration_min'])}min" if s["duration_min"] else "?"
            pwr = f"@{s['power_low']}-{s['power_high']}W" if s["power_low"] else ""
            split_descs.append(f"{dur}{pwr}")

            # Track the highest power split as the "main set"
            if s["power_high"] and s["power_high"] > max_power:
                max_power = s["power_high"]
                main_power_low = s["power_low"]
                main_power_high = s["power_high"]

        if not split_descs:
            continue

        name = section["name"]
        repeat = section["splits"][0]["repeat"] if section["splits"] else 1

        if name.lower() == "run/recover" and len(split_descs) == 2:
            desc_parts.append(f"{repeat}x({split_descs[0]} + Recover {split_descs[1]})")
        elif repeat > 1:
            desc_parts.append(f"{name} {repeat}x{split_descs[0]}")
        else:
            for sd in split_descs:
                desc_parts.append(f"{name} {sd}")

    description = " | ".join(desc_parts)
    return description, main_power_low, main_power_high


def _close_modal(page) -> None:
    """Close any open modal/overlay."""
    close_btn = page.query_selector(
        "button[aria-label*='close'], button:has(img[alt*='close'])"
    )
    if close_btn:
        close_btn.click()
    else:
        page.keyboard.press("Escape")
    page.wait_for_timeout(500)


def scrape_stryd(
    user_id: str,
    email: str | None = None,
    password: str | None = None,
    token: str | None = None,
    from_date: str | None = None,
) -> tuple[list[dict], list[dict]]:
    """Scrape both completed activities and upcoming plan from Stryd calendar.

    Returns (activity_rows, plan_rows) where:
    - activity_rows: list of dicts matching power_data.csv schema
    - plan_rows: list of dicts matching parse_training_plan() input schema
    """
    from playwright.sync_api import sync_playwright

    if not (email and password) and not token:
        raise ValueError("Either email+password or token must be provided")

    calendar_url = STRYD_CALENDAR_URL.format(user_id=user_id)
    activity_rows = []
    plan_workouts = []

    today = date.today()
    start = datetime.strptime(from_date, "%Y-%m-%d").date() if from_date else today - timedelta(days=7)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Authenticate
        if email and password:
            _login_with_credentials(page, email, password, calendar_url)
        else:
            _login_with_token(page, token, calendar_url)

        page.wait_for_selector("h3", timeout=30000)
        page.wait_for_timeout(3000)

        # Click "Today" button to anchor the calendar to the current date,
        # then scroll to top to reveal the beginning of the month
        today_btn = page.query_selector("button:has-text('Today')")
        if today_btn:
            today_btn.click()
            page.wait_for_timeout(2000)

        # Debug: print what heading we see
        heading = page.query_selector("h3")
        heading_text = heading.inner_text().strip() if heading else "NO HEADING"
        print(f"  Calendar heading after 'Today' click: '{heading_text}'")

        # Detect which month the calendar is actually showing (may differ
        # from today's month — e.g. "Today" click can land on the next month)
        displayed_year, displayed_month = _get_calendar_month_year(page)
        print(f"  Calendar is on: {displayed_year}-{displayed_month:02d}")

        # Always navigate to the start month — don't assume the calendar
        # is on today's month (it may have landed on a different month)
        _navigate_calendar_to_month(page, start.year, start.month)
        page.wait_for_timeout(1500)

        # Process all months from start through whichever is later:
        # today's month or the month the calendar initially showed
        months_to_process = []
        cursor = date(start.year, start.month, 1)
        end_month = max(
            date(today.year, today.month, 1),
            date(displayed_year, displayed_month, 1),
        )
        while cursor <= end_month:
            months_to_process.append((cursor.year, cursor.month))
            if cursor.month == 12:
                cursor = date(cursor.year + 1, 1, 1)
            else:
                cursor = date(cursor.year, cursor.month + 1, 1)

        for month_idx, (target_year, target_month) in enumerate(months_to_process):
            if month_idx > 0:
                # Navigate forward to next month
                buttons = page.query_selector_all("button")
                for i, btn in enumerate(buttons):
                    if btn.inner_text().strip() == "Today":
                        # Next month button is 2 after Today
                        if i + 2 < len(buttons):
                            buttons[i + 2].click()
                            page.wait_for_timeout(1500)
                        break

            current_year, current_month = _get_calendar_month_year(page)
            print(f"  Stryd calendar: {current_year}-{current_month:02d}")

            # Scroll the calendar to the top so past weeks' activities are
            # loaded into the DOM. The calendar lazy-renders by week and
            # defaults to showing the current week, hiding earlier weeks above.
            _scroll_calendar_to_top(page)

            # --- Scrape completed activities ---
            # Completed activities on the calendar show as cards with:
            #   - A time pattern: either "H:MM:SS" duration or "H:MM AM/PM" clock time
            #   - "RSS" text with a numeric value
            # Tag only leaf-level matches (no child that also matches).
            activity_count = page.evaluate("""() => {
                // Completed activities have duration + km + RSS but NO "Day N -" prefix
                // Plan items have "Day N -" prefix (e.g., "Day 51 - Easy")
                const durationPattern = /\\d{1,2}:\\d{2}(?::\\d{2})?/;
                const els = document.querySelectorAll('div, span, a');
                const matches = [];
                for (const el of els) {
                    const t = el.innerText || '';
                    if (t.length > 200) continue;
                    // Must have RSS with a numeric value
                    if (!(/\\d+\\s*RSS/.test(t))) continue;
                    // Must have a time/duration pattern
                    if (!durationPattern.test(t)) continue;
                    // Exclude plan workouts (have "Day N -" text)
                    if (/Day\\s+\\d+\\s*-/.test(t)) continue;
                    matches.push(el);
                }
                // Keep only leaf matches: skip any element that has a descendant also in matches
                const matchSet = new Set(matches);
                let count = 0;
                for (const el of matches) {
                    const hasChildMatch = matches.some(other => other !== el && el.contains(other));
                    if (!hasChildMatch) {
                        el.setAttribute('data-stryd-activity', count);
                        count++;
                    }
                }
                return count;
            }""")
            print(f"    Found {activity_count} activity elements on calendar")
            if activity_count == 0:
                sample = page.evaluate("""() => {
                    const els = document.querySelectorAll('div, span, a');
                    const samples = [];
                    for (const el of els) {
                        const t = (el.innerText || '').trim();
                        if (t.length > 10 && t.length < 100 && /\\d/.test(t)) {
                            samples.push(t.substring(0, 80));
                            if (samples.length >= 5) break;
                        }
                    }
                    return samples;
                }""")
                print(f"    DEBUG: No activities matched. Sample DOM text: {sample}")
            for idx in range(activity_count):
                el = page.query_selector(f"[data-stryd-activity='{idx}']")
                if not el:
                    continue

                try:
                    el.click()
                    page.wait_for_timeout(2000)

                    stats = _scrape_activity_detail(page)
                    if stats.get("date_str"):
                        act_date = datetime.strptime(stats["date_str"], "%Y-%m-%d").date()
                        print(f"    Activity {idx}: {stats['date_str']} (RSS={stats.get('rss', '?')})")
                        if act_date < start or act_date > today:
                            _close_modal(page)
                            continue
                    else:
                        print(f"    Activity {idx}: no date found in detail view")

                    row = parse_activity_detail(stats)
                    activity_rows.append(row)

                    _close_modal(page)
                except Exception as e:
                    print(f"    Activity {idx}: ERROR scraping detail — {type(e).__name__}: {e}")
                    try:
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(500)
                    except Exception:
                        pass

            # --- Scrape planned workouts ---
            # The workout name (e.g. "Day 46 - Steady Aerobic") is in a <p> tag.
            # Its parent container has sibling <p> elements with duration, distance, RSS.
            # Find the <p> with "Day N -", then walk up to the clickable container.
            plan_count = page.evaluate("""() => {
                const paragraphs = document.querySelectorAll('p');
                let count = 0;
                for (const p of paragraphs) {
                    const t = p.textContent.trim();
                    if (!/^Day\\s+\\d+\\s*-/.test(t)) continue;

                    // Walk up to find the nearest clickable ancestor
                    let container = p.parentElement;
                    for (let i = 0; i < 5 && container; i++) {
                        const style = window.getComputedStyle(container);
                        if (style.cursor === 'pointer' || container.tagName === 'BUTTON' || container.tagName === 'A') {
                            break;
                        }
                        container = container.parentElement;
                    }
                    if (!container) continue;

                    // Skip if this is a completed activity (has AM/PM time)
                    const containerText = container.innerText || '';
                    if (/\\d{1,2}:\\d{2}\\s*[AP]M/.test(containerText)) continue;

                    // Skip if already tagged as activity
                    if (container.hasAttribute('data-stryd-activity')) continue;

                    container.setAttribute('data-stryd-plan', count);
                    count++;
                }
                return count;
            }""")
            for idx in range(plan_count):
                btn = page.query_selector(f"[data-stryd-plan='{idx}']")
                if not btn:
                    continue

                try:
                    btn.click()
                    page.wait_for_timeout(2000)

                    # Extract date, title, power, duration, distance, and full text from the modal
                    modal_data = page.evaluate("""() => {
                        const data = {};

                        // Find the modal/dialog container to scope our search
                        const modal = document.querySelector('dialog, [role="dialog"]')
                            || document.querySelector('[class*="modal"], [class*="Modal"], [class*="overlay"], [class*="Overlay"]');

                        // Heading with date: "March 19, 2026 at 10:00 AM"
                        const headings = document.querySelectorAll('dialog h2, [role="dialog"] h2, h2');
                        for (const h of headings) {
                            const t = h.innerText.trim();
                            const m = t.match(/(\\w+ \\d+, \\d{4})/);
                            if (m) { data.date_header = m[1]; break; }
                        }

                        // Workout title: "Day 46 - Steady Aerobic" (h2)
                        for (const h of headings) {
                            const t = h.innerText.trim();
                            if (/^Day\\s+\\d+\\s*-/.test(t)) { data.title = t; break; }
                        }

                        // Scan elements within modal for duration and distance
                        // Collect ALL durations and distances, then pick the best
                        const searchRoot = modal || document;
                        const allEls = searchRoot.querySelectorAll('p, span, div, td, h3, h4');
                        const durations = [];
                        const distances = [];
                        for (const el of allEls) {
                            if (el.querySelector('p, span, div, td, h3, h4')) continue;
                            const t = el.textContent.trim();
                            if (/^\\d+:\\d{2}(:\\d{2})?$/.test(t)) {
                                durations.push(t);
                            }
                            if (/^[\\d.]+\\s*km$/i.test(t)) {
                                distances.push(t);
                            }
                        }
                        // Pick the longest duration (total workout, not a split)
                        if (durations.length > 0) {
                            const toSec = (d) => {
                                const p = d.split(':').map(Number);
                                return p.length === 3 ? p[0]*3600+p[1]*60+p[2] : p[0]*60+p[1];
                            };
                            durations.sort((a, b) => toSec(b) - toSec(a));
                            data.duration = durations[0];
                        }
                        // Pick the longest distance (total workout distance)
                        if (distances.length > 0) {
                            distances.sort((a, b) => {
                                const va = parseFloat(a);
                                const vb = parseFloat(b);
                                return vb - va;
                            });
                            data.distance = distances[0];
                        }

                        // Power target: extract from modal text (handles any dash variant)
                        const modalText = modal ? modal.innerText : document.body.innerText;
                        const pm = modalText.match(/(\\d+)\\s*[\\-\\u2013\\u2014]\\s*(\\d+)\\s*W/);
                        if (pm) {
                            data.power_low = parseInt(pm[1]);
                            data.power_high = parseInt(pm[2]);
                        }

                        // Full modal text for structured interval parsing
                        data.modal_text = modalText;

                        return data;
                    }""")

                    if not modal_data.get("date_header") or not modal_data.get("title"):
                        _close_modal(page)
                        continue

                    # Parse date
                    try:
                        dt = datetime.strptime(modal_data["date_header"], "%B %d, %Y")
                        workout_date = dt.strftime("%Y-%m-%d")
                    except ValueError:
                        _close_modal(page)
                        continue

                    # Only include today and future workouts
                    if datetime.strptime(workout_date, "%Y-%m-%d").date() < today:
                        _close_modal(page)
                        continue

                    # Extract structured intervals and power from modal text
                    description, power_low, power_high = _parse_structured_intervals(
                        modal_data.get("modal_text", "")
                    )

                    # Fall back to JS-extracted power if Python parsing didn't find it
                    if power_low is None and modal_data.get("power_low"):
                        power_low = modal_data["power_low"]
                        power_high = modal_data.get("power_high")

                    # Duration and distance from modal
                    # For simple workouts, the modal has a standalone duration element.
                    # For structured workouts, the total is the sum of split durations,
                    # and distance may be in a distance-based split (e.g., "25.00 km").
                    modal_duration = modal_data.get("duration")
                    modal_distance = modal_data.get("distance")
                    duration_min = _parse_duration_to_minutes(modal_duration) if modal_duration else None
                    distance_km = _parse_distance_km(modal_distance) if modal_distance else None

                    # For structured workouts: compute total duration from splits
                    # and extract distance from distance-based splits
                    modal_text = modal_data.get("modal_text", "")
                    split_durations = re.findall(r"S:\d+\s+(\d+:\d{2}(?::\d{2})?)\s+(?:Run|Warmup|Cooldown|Recover)", modal_text)
                    split_distances = re.findall(r"S:\d+\s+([\d.]+)\s*km\s+(?:Run|Warmup|Cooldown|Recover)", modal_text, re.IGNORECASE)
                    if split_durations:
                        total_min = sum(_parse_duration_to_minutes(d) or 0 for d in split_durations)
                        if total_min > (duration_min or 0):
                            duration_min = total_min
                    if split_distances and not distance_km:
                        # Use the largest distance split (the main set)
                        distance_km = max(float(d) for d in split_distances)

                    parsed = {
                        "date": workout_date,
                        "workout_type": _workout_type_from_name(modal_data["title"]),
                        "duration_minutes": duration_min,
                        "distance_km": distance_km,
                        "power_target_low": power_low,
                        "power_target_high": power_high,
                        "workout_description": description,
                    }
                    plan_workouts.append(parsed)

                    _close_modal(page)
                except Exception as e:
                    print(f"    Plan workout {idx}: ERROR — {type(e).__name__}: {e}")
                    try:
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(500)
                    except Exception:
                        pass

        browser.close()

    return activity_rows, plan_workouts


# --- API-based fetch (primary method) ---

STRYD_LOGIN_URL = "https://www.stryd.com/b/email/signin"
STRYD_CALENDAR_API = "https://api.stryd.com/b/api/v1/users/{user_id}/calendar"


def _login_api(email: str, password: str) -> tuple[str, str]:
    """Login via Stryd API. Returns (user_id, token)."""
    print("  Logging in via Stryd API...")
    resp = requests.post(
        STRYD_LOGIN_URL,
        json={"email": email, "password": password},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    user_id = data.get("id", "")
    token = data.get("token", "")
    if not token:
        raise RuntimeError("Login succeeded but no token in response")
    print(f"  Login successful (user_id={user_id})")
    return user_id, token


def fetch_activities_api(
    user_id: str,
    token: str,
    from_date: str,
    to_date: str | None = None,
) -> list[dict]:
    """Fetch completed activities from the Stryd calendar API.

    Args:
        user_id: Stryd user UUID.
        token: Bearer token for Stryd API.
        from_date: Start date (YYYY-MM-DD).
        to_date: End date (YYYY-MM-DD), defaults to today.

    Returns:
        List of dicts matching power_data.csv schema.
    """
    start_dt = datetime.strptime(from_date, "%Y-%m-%d")
    end_dt = datetime.strptime(to_date, "%Y-%m-%d") if to_date else datetime.now()
    # Add a day to end to include activities on the end date
    end_dt = end_dt.replace(hour=23, minute=59, second=59)

    from_ts = int(start_dt.timestamp())
    to_ts = int(end_dt.timestamp())

    url = STRYD_CALENDAR_API.format(user_id=user_id)
    resp = requests.get(
        url,
        params={"from": from_ts, "to": to_ts, "include_deleted": "false"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    activities = data.get("activities", [])
    print(f"  API returned {len(activities)} activities")

    rows = []
    for act in activities:
        # Convert unix timestamp to local datetime using the activity's timezone
        tz_name = act.get("time_zone", "UTC")
        try:
            from zoneinfo import ZoneInfo
            local_tz = ZoneInfo(tz_name)
        except (ImportError, KeyError):
            local_tz = timezone.utc
        start_unix = act.get("start_time") or act.get("timestamp")
        if not start_unix:
            continue
        start_utc = datetime.fromtimestamp(start_unix, tz=timezone.utc)
        start_local = start_utc.astimezone(local_tz)

        distance_m = act.get("distance", 0) or 0
        distance_km = round(distance_m / 1000, 2)
        moving_time = act.get("moving_time") or act.get("elapsed_time")

        row = {
            "date": start_local.strftime("%Y-%m-%d"),
            "start_time": start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "avg_power": _round_or_empty(act.get("average_power")),
            "max_power": _round_or_empty(act.get("max_power")),
            "form_power": "",
            "leg_spring_stiffness": _round_or_empty(act.get("average_leg_spring")),
            "ground_time_ms": _round_or_empty(act.get("average_ground_time")),
            "rss": _round_or_empty(act.get("stress")),
            "cp_estimate": _round_or_empty(act.get("ftp")),
            "distance_km": str(distance_km),
            "duration_sec": str(moving_time) if moving_time is not None else "",
        }
        print(f"    {row['date']} — {row['avg_power']}W, {row['distance_km']}km, RSS={row['rss']}")
        rows.append(row)

    return rows


def fetch_training_plan_api(
    user_id: str,
    token: str,
    cp_watts: float | None = None,
    days_ahead: int = 14,
) -> list[dict]:
    """Fetch upcoming planned workouts from the Stryd calendar API.

    The API returns planned workouts under the 'workouts' key (separate from
    completed 'activities'). Each workout has structured blocks with segments
    containing intensity as CP percentage.

    Args:
        cp_watts: Current CP in watts (for converting % targets to absolute watts).
                  If None, power targets are omitted.
    """
    today = date.today()
    end = today + timedelta(days=days_ahead)

    from_ts = int(datetime.combine(today, datetime.min.time()).timestamp())
    to_ts = int(datetime.combine(end, datetime.max.time()).timestamp())

    url = STRYD_CALENDAR_API.format(user_id=user_id)
    resp = requests.get(
        url,
        params={"from": from_ts, "to": to_ts, "include_deleted": "false"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    workouts = data.get("workouts", [])
    print(f"  Plan API returned {len(workouts)} planned workouts")

    rows = []
    for item in workouts:
        if item.get("deleted"):
            continue

        # Parse date from ISO format: "2026-04-04T02:00:00Z"
        date_str = item.get("date", "")
        try:
            workout_date = datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            continue

        workout_info = item.get("workout", {})
        title = workout_info.get("title", "")
        workout_type = workout_info.get("type", "") or _workout_type_from_name(title)

        # Total duration and distance from the top-level summary
        duration_sec = item.get("duration", 0) or 0
        duration_min = round(duration_sec / 60, 1) if duration_sec else ""

        distance_m = item.get("distance", 0) or 0
        distance_km = round(distance_m / 1000, 1) if distance_m else ""

        # Extract power targets from the "work" segment blocks
        # Intensity is specified as percentage of CP
        power_min = ""
        power_max = ""
        blocks = workout_info.get("blocks", [])
        for block in blocks:
            for seg in block.get("segments", []):
                if seg.get("intensity_class") == "work":
                    pct = seg.get("intensity_percent", {})
                    pct_min = pct.get("min", 0)
                    pct_max = pct.get("max", 0)
                    if cp_watts and pct_min and pct_max:
                        power_min = str(round(cp_watts * pct_min / 100))
                        power_max = str(round(cp_watts * pct_max / 100))
                    break
            if power_min:
                break

        # Build workout description from blocks
        desc_parts = []
        for block in blocks:
            repeat = block.get("repeat", 1)
            for seg in block.get("segments", []):
                cls = seg.get("intensity_class", "")
                dur = seg.get("duration_time", {})
                dur_str = ""
                if dur.get("hour"):
                    dur_str = f"{dur['hour']}h{dur.get('minute', 0):02d}m"
                elif dur.get("minute"):
                    dur_str = f"{dur['minute']}min"

                dist = seg.get("duration_distance", 0)
                dist_unit = seg.get("distance_unit_selected", "")
                dist_str = f"{dist}{dist_unit}" if dist else ""

                pct = seg.get("intensity_percent", {})
                pct_str = f"@{pct.get('min', 0)}-{pct.get('max', 0)}%CP" if pct.get("min") else ""

                part = f"{cls}: {dur_str or dist_str} {pct_str}".strip()
                if repeat > 1:
                    part = f"{repeat}x({part})"
                desc_parts.append(part)

        description = " | ".join(desc_parts) if desc_parts else title

        row = {
            "date": workout_date,
            "workout_type": workout_type,
            "planned_duration_min": str(duration_min) if duration_min else "",
            "planned_distance_km": str(distance_km) if distance_km else "",
            "target_power_min": power_min,
            "target_power_max": power_max,
            "workout_description": description,
        }
        print(f"    {workout_date} — {workout_type} ({duration_min}min, {distance_km}km)")
        rows.append(row)

    return rows


def _round_or_empty(val) -> str:
    """Round a numeric value to 1 decimal, or return empty string if None."""
    if val is None:
        return ""
    return str(round(float(val), 1))


# --- Sync entry point ---


def sync(
    user_id: str,
    data_dir: str,
    email: str | None = None,
    password: str | None = None,
    token: str | None = None,
    from_date: str | None = None,
) -> None:
    """Pull Stryd data and save to CSVs.

    Auth strategy:
    1. If STRYD_TOKEN is set, use it directly for API calls
    2. If not, login via Stryd API with email/password to get token
    3. Last resort: fall back to full Playwright scraper
    """
    start = from_date or (date.today() - timedelta(days=7)).isoformat()
    print(f"Stryd: syncing from {start}")

    activity_rows = []
    plan_rows = []

    # Step 1: Acquire token if we don't have one
    if not token and email and password:
        try:
            api_user_id, token = _login_api(email, password)
            # Use the API-returned user_id if the caller passed a placeholder
            if not user_id or user_id == "me":
                user_id = api_user_id
        except Exception as e:
            print(f"  API login failed ({e}), trying browser fallback...")
            try:
                token = _acquire_token_via_browser(email, password)
            except Exception as e2:
                print(f"  Browser login also failed ({e2})")

    # Step 2: Try API with token
    if token:
        try:
            activity_rows = fetch_activities_api(user_id, token, from_date=start)
        except requests.HTTPError as e:
            status = e.response.status_code
            print(f"  Stryd API failed (HTTP {status})")
            # If 401 and we have credentials, try re-login
            if status == 401 and email and password:
                try:
                    print("  Re-acquiring token...")
                    _, token = _login_api(email, password)
                    activity_rows = fetch_activities_api(user_id, token, from_date=start)
                except Exception as e2:
                    print(f"  Re-login failed ({e2})")
        except Exception as e:
            print(f"  Stryd API failed ({e})")

        # Also fetch training plan via API
        if token:
            try:
                # Get CP from the most recent activity for power target conversion
                cp_watts = None
                if activity_rows:
                    for row in activity_rows:
                        cp_val = row.get("cp_estimate", "")
                        if cp_val:
                            cp_watts = float(cp_val)
                            break
                plan_rows = fetch_training_plan_api(user_id, token, cp_watts=cp_watts)
            except Exception as e:
                print(f"  Training plan API failed ({e})")

    # Step 3: Last resort — full Playwright scraper
    if not activity_rows:
        print("  Falling back to Playwright scraper...")
        try:
            activity_rows, raw_plan = scrape_stryd(
                user_id=user_id,
                email=email,
                password=password,
                token=token,
                from_date=start,
            )
            if raw_plan and not plan_rows:
                plan_rows = parse_training_plan(raw_plan)
        except ImportError:
            print("  Stryd: skipped (no token and playwright not installed)")
            return
        except Exception as e:
            print(f"  Stryd: scraper also failed ({e})")
            return

    if activity_rows:
        power_path = os.path.join(data_dir, "stryd", "power_data.csv")
        append_rows(power_path, activity_rows, key_column="start_time")
        print(f"  Saved {len(activity_rows)} activities to power_data.csv")

    if plan_rows:
        plan_path = os.path.join(data_dir, "stryd", "training_plan.csv")
        append_rows(plan_path, plan_rows, key_column="date")
        print(f"  Saved {len(plan_rows)} planned workouts to training_plan.csv")


if __name__ == "__main__":
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    parser = argparse.ArgumentParser(description="Sync Stryd data")
    parser.add_argument("--from-date", help="Start date (YYYY-MM-DD) for historical backfill")
    args = parser.parse_args()

    user_id = os.environ["STRYD_USER_ID"]
    email = os.environ.get("STRYD_EMAIL")
    password = os.environ.get("STRYD_PASSWORD")
    token = os.environ.get("STRYD_TOKEN")
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    sync(user_id, data_dir, email=email, password=password, token=token, from_date=args.from_date)
