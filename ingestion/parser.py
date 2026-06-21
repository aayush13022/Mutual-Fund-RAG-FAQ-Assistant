"""Groww mutual fund page parser with 9-section extraction."""

from __future__ import annotations

import logging
import re
from typing import Iterable

from bs4 import BeautifulSoup, Tag

from config.settings import REQUIRED_SECTIONS
from ingestion.models import FundManager, ParsedSection

logger = logging.getLogger(__name__)

SECTION_TYPES = tuple(sorted(REQUIRED_SECTIONS))


def _clean_line(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _find_heading(soup: BeautifulSoup, tags: Iterable[str], label: str, *, exact: bool = True) -> Tag | None:
    for tag_name in tags:
        for element in soup.find_all(tag_name):
            text = element.get_text(strip=True)
            if exact and text == label:
                return element
            if not exact and label.lower() in text.lower() and len(text) <= len(label) + 40:
                return element
    return None


def _container_text(heading: Tag, *, max_depth: int = 6) -> str:
    container = heading.parent
    for _ in range(max_depth):
        if container is None:
            break
        text = container.get_text("\n", strip=True)
        if len(text) > len(heading.get_text(strip=True)) + 20:
            return text
        container = container.parent
    return heading.get_text("\n", strip=True)


def _section_after_heading(heading: Tag) -> str:
    lines = [heading.get_text(strip=True)]
    sibling = heading.find_next_sibling()
    while sibling is not None:
        if isinstance(sibling, Tag) and sibling.name in {"h2", "h3", "h4", "h5"}:
            break
        chunk = sibling.get_text(" ", strip=True) if isinstance(sibling, Tag) else str(sibling).strip()
        if chunk:
            lines.append(chunk)
        sibling = sibling.find_next_sibling()
    return _clean_line("\n".join(lines))


def _extract_overview(soup: BeautifulSoup, scheme_name: str) -> ParsedSection:
    fields: dict[str, str] = {"scheme_name": scheme_name}

    h1 = soup.find("h1")
    if h1:
        fields["scheme_name"] = h1.get_text(strip=True)
        header_area = h1.parent.get_text("\n", strip=True) if h1.parent else ""
        category_match = re.search(
            r"(Equity|Debt|Hybrid|Other|Solution Oriented)[^\n]*(?:\n[^\n]+)?",
            header_area,
            re.I,
        )
        if category_match:
            fields["category"] = _clean_line(category_match.group(0))
        risk_match = re.search(r"(Very High|High|Moderately High|Moderate|Low to Moderate|Low) Risk", header_area, re.I)
        if risk_match:
            fields["risk"] = risk_match.group(0)

    metrics_text = ""
    for div in soup.find_all("div"):
        text = div.get_text(strip=True)
        if text.startswith("NAV:") and "Expense ratio" in text and len(text) < 350:
            metrics_text = text
            break

    if metrics_text:
        nav_match = re.search(r"NAV:\s*[^₹]*₹([\d,.]+)", metrics_text)
        if nav_match:
            fields["nav"] = f"₹{nav_match.group(1)}"
        nav_date_match = re.search(r"NAV:\s*([\d]{1,2}\s+\w{3}\s+'?\d{2})", metrics_text)
        if nav_date_match:
            fields["nav_date"] = nav_date_match.group(1)
        aum_match = re.search(r"Fund size \(AUM\)\s*₹([\d,.]+)\s*Cr", metrics_text)
        if aum_match:
            fields["aum"] = f"₹{aum_match.group(1)} Cr"
        sip_match = re.search(r"Min\. for SIP\s*₹?([\d,.]+|Not Supported)", metrics_text)
        if sip_match:
            fields["min_sip"] = sip_match.group(1)
        expense_match = re.search(r"Expense ratio\s*([\d.]+%|--)", metrics_text)
        if expense_match:
            fields["expense_ratio"] = expense_match.group(1)

    lines = [f"Scheme: {fields.get('scheme_name', scheme_name)}"]
    for key, label in [
        ("category", "Category"),
        ("risk", "Risk"),
        ("nav", "NAV"),
        ("nav_date", "NAV date"),
        ("aum", "AUM"),
        ("min_sip", "Min SIP"),
        ("expense_ratio", "Expense ratio"),
    ]:
        if key in fields:
            lines.append(f"{label}: {fields[key]}")

    return ParsedSection(section_type="overview", text="\n".join(lines), fields=fields)


def _extract_expense_ratio(soup: BeautifulSoup) -> ParsedSection | None:
    value = ""
    for div in soup.find_all("div"):
        text = div.get_text(strip=True)
        if text.startswith("NAV:") and "Expense ratio" in text:
            match = re.search(r"Expense ratio\s*([\d.]+%|--)", text)
            if match:
                value = match.group(1)
                break

    heading = _find_heading(soup, ("h5", "h4", "span"), "Expense ratio")
    if heading and not value:
        parent_text = heading.parent.get_text(" ", strip=True) if heading.parent else ""
        match = re.search(r"Expense ratio\s*([\d.]+%|--)", parent_text)
        if match:
            value = match.group(1)

    if not value:
        return None

    return ParsedSection(
        section_type="expense_ratio",
        text=f"Expense ratio (direct plan): {value}",
        fields={"expense_ratio": value},
    )


def _extract_exit_load(soup: BeautifulSoup) -> ParsedSection | None:
    heading = _find_heading(soup, ("h4",), "Exit load")
    if heading is None:
        heading = _find_heading(soup, ("h3",), "Exit load, stamp duty and tax", exact=False)
    if heading is None:
        return None

    text = _section_after_heading(heading)
    if heading.name == "h3":
        h4 = heading.find_next("h4", string=re.compile(r"^Exit load$", re.I))
        if h4:
            text = _section_after_heading(h4)

    text = re.sub(r"^Exit load\s*", "", text, flags=re.I).strip()
    if not text or text.lower() == "exit load":
        return None

    stamp_duty = ""
    stamp_heading = _find_heading(soup, ("h4", "h5"), "Stamp duty", exact=False)
    if stamp_heading:
        stamp_duty = _section_after_heading(stamp_heading)

    combined = f"Exit load: {text}"
    if stamp_duty:
        combined += f"\nStamp duty: {stamp_duty}"

    return ParsedSection(
        section_type="exit_load",
        text=combined,
        fields={"exit_load": text, "stamp_duty": stamp_duty},
    )


def _extract_minimum_investment(soup: BeautifulSoup) -> ParsedSection | None:
    heading = _find_heading(soup, ("h3",), "Minimum investments")
    if heading is None:
        return None

    text = _container_text(heading)
    fields: dict[str, str] = {}
    patterns = {
        "min_first_investment": r"Min\. for 1st investment\s*([^\n]+)",
        "min_second_investment": r"Min\. for 2nd investment\s*([^\n]+)",
        "min_sip": r"Min\. for SIP\s*([^\n]+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.I)
        if match:
            fields[key] = _clean_line(match.group(1))

    if not fields:
        return None

    lines = ["Minimum investments:"]
    labels = {
        "min_first_investment": "Min. for 1st investment",
        "min_second_investment": "Min. for 2nd investment",
        "min_sip": "Min. for SIP",
    }
    for key, label in labels.items():
        if key in fields:
            lines.append(f"{label}: {fields[key]}")

    return ParsedSection(section_type="minimum_investment", text="\n".join(lines), fields=fields)


def _extract_benchmark(soup: BeautifulSoup) -> ParsedSection | None:
    benchmark = ""
    for span in soup.find_all("span"):
        if span.get_text(strip=True) == "Fund benchmark":
            parent_text = span.parent.get_text("\n", strip=True) if span.parent else ""
            lines = [line for line in parent_text.splitlines() if line.strip() and line.strip() != "Fund benchmark"]
            if lines:
                benchmark = _clean_line(lines[0])
            break

    if not benchmark:
        heading = _find_heading(soup, ("h4", "h5", "span"), "Fund benchmark", exact=False)
        if heading:
            text = _container_text(heading)
            match = re.search(r"Fund benchmark\s*(.+)", text, re.I | re.S)
            if match:
                benchmark = _clean_line(match.group(1).split("Scheme Information")[0])

    if not benchmark:
        return None

    return ParsedSection(
        section_type="benchmark",
        text=f"Fund benchmark: {benchmark}",
        fields={"benchmark": benchmark},
    )


def _extract_tax(soup: BeautifulSoup) -> ParsedSection | None:
    heading = _find_heading(soup, ("h4",), "Tax implication")
    if heading is None:
        return None

    text = _section_after_heading(heading)
    text = re.sub(r"^Tax implication\s*", "", text, flags=re.I).strip()
    if not text:
        return None

    return ParsedSection(section_type="tax", text=f"Tax implication: {text}", fields={"tax_implication": text})


def _parse_manager_blocks(block_text: str) -> list[FundManager]:
    text = block_text.replace("View details", "\n")
    chunks = re.split(r"(?=Also manages these schemes)", text)
    managers: list[FundManager] = []

    for chunk in chunks:
        if "Education" not in chunk:
            continue

        lines = [line.strip() for line in chunk.splitlines() if line.strip()]
        name = ""
        tenure = ""
        education = ""
        experience = ""
        other_schemes: list[str] = []

        name_idx = None
        for idx, line in enumerate(lines):
            if re.fullmatch(r"[A-Z]{2}", line):
                if idx + 1 < len(lines):
                    candidate = lines[idx + 1]
                    if not re.search(r"education|experience|also manages", candidate, re.I):
                        name = candidate
                        name_idx = idx + 1
                        break

        if not name:
            continue

        tenure_parts: list[str] = []
        for line in lines[name_idx + 1 :]:
            if line in {"-", "Present"} or re.match(r"^[A-Z][a-z]{2}\s+\d{4}$", line):
                tenure_parts.append(line)
                continue
            if line.lower() == "education":
                break
            if tenure_parts:
                break
        tenure = _clean_line(" ".join(tenure_parts))

        edu_match = re.search(r"Education\s*(.+?)(?:Experience|Also manages these schemes|$)", chunk, re.I | re.S)
        if edu_match:
            education = _clean_line(edu_match.group(1))

        exp_match = re.search(r"Experience\s*(.+?)(?:Also manages these schemes|$)", chunk, re.I | re.S)
        if exp_match:
            experience = _clean_line(exp_match.group(1))

        schemes_match = re.search(r"Also manages these schemes\s*(.+)$", chunk, re.I | re.S)
        if schemes_match:
            scheme_lines = [
                _clean_line(line)
                for line in schemes_match.group(1).splitlines()
                if _clean_line(line) and "Also manages" not in line
            ]
            other_schemes = scheme_lines

        managers.append(
            FundManager(
                name=name,
                tenure=tenure,
                education=education,
                experience=experience,
                other_schemes=tuple(other_schemes),
            )
        )

    return managers


def _extract_fund_management(soup: BeautifulSoup) -> ParsedSection | None:
    heading = _find_heading(soup, ("h3",), "Fund management")
    if heading is None:
        return None

    block_text = _container_text(heading, max_depth=8)
    block_text = re.sub(r"^Fund management\s*", "", block_text, flags=re.I).strip()
    managers = _parse_manager_blocks(block_text)

    if not managers:
        return None

    lines = ["Fund management:"]
    fields: dict[str, str] = {}
    for index, manager in enumerate(managers, start=1):
        prefix = f"manager_{index}"
        fields[f"{prefix}_name"] = manager.name
        fields[f"{prefix}_tenure"] = manager.tenure
        fields[f"{prefix}_education"] = manager.education
        fields[f"{prefix}_experience"] = manager.experience
        lines.append(f"Manager {index}: {manager.name}")
        if manager.tenure:
            lines.append(f"Tenure: {manager.tenure}")
        if manager.education:
            lines.append(f"Education: {manager.education}")
        if manager.experience:
            lines.append(f"Experience: {manager.experience}")
        if manager.other_schemes:
            lines.append("Also manages: " + "; ".join(manager.other_schemes[:5]))
            if len(manager.other_schemes) > 5:
                lines.append(f"(+{len(manager.other_schemes) - 5} more schemes)")

    return ParsedSection(
        section_type="fund_management",
        text="\n".join(lines),
        fields=fields,
        managers=managers,
    )


def _extract_investment_objective(soup: BeautifulSoup) -> ParsedSection | None:
    heading = _find_heading(soup, ("h4",), "Investment Objective")
    if heading is None:
        return None

    text = _section_after_heading(heading)
    text = re.sub(r"^Investment Objective\s*", "", text, flags=re.I).strip()
    if not text:
        return None

    return ParsedSection(
        section_type="investment_objective",
        text=f"Investment objective: {text}",
        fields={"investment_objective": text},
    )


def _extract_fund_house(soup: BeautifulSoup) -> ParsedSection | None:
    headings = [h for h in soup.find_all("h3") if h.get_text(strip=True) == "Fund house"]
    heading = None
    for candidate in headings:
        container_text = _container_text(candidate)
        if "Date of Incorporation" in container_text or "Launch Date" in container_text:
            heading = candidate
            break
    if heading is None and headings:
        heading = headings[-1]
    if heading is None:
        return None

    text = _container_text(heading, max_depth=10)
    fields: dict[str, str] = {}

    patterns = {
        "amc_name": r"^Fund house\s*\n?([^\n]+)",
        "launch_date": r"Launch Date\s*([^\n]+)",
        "date_of_incorporation": r"Date of Incorporation\s*([^\n]+)",
        "website": r"Website\s*(https?://[^\s\n]+|www\.[^\s\n]+)",
        "address": r"Address\s*([^\n]+(?:\n[^\n]+)?)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.I | re.M)
        if match:
            fields[key] = _clean_line(match.group(1))

    amc_line_match = re.search(r"Fund house\s*\n([^\n]+)", text)
    if amc_line_match and "amc_name" not in fields:
        fields["amc_name"] = _clean_line(amc_line_match.group(1))

    lines = ["Fund house:"]
    if "amc_name" in fields:
        lines.append(f"AMC: {fields['amc_name']}")
    for key, label in [
        ("launch_date", "Launch date"),
        ("date_of_incorporation", "Date of incorporation"),
        ("website", "Website"),
        ("address", "Address"),
    ]:
        if key in fields:
            lines.append(f"{label}: {fields[key]}")

    return ParsedSection(section_type="fund_house", text="\n".join(lines), fields=fields)


def parse_html(html: str, *, scheme_name: str, source_url: str) -> list[ParsedSection]:
    """Parse Groww HTML into normalized section records."""
    soup = BeautifulSoup(html, "html.parser")

    extractors = [
        lambda: _extract_overview(soup, scheme_name),
        lambda: _extract_expense_ratio(soup),
        lambda: _extract_exit_load(soup),
        lambda: _extract_minimum_investment(soup),
        lambda: _extract_benchmark(soup),
        lambda: _extract_tax(soup),
        lambda: _extract_fund_management(soup),
        lambda: _extract_investment_objective(soup),
        lambda: _extract_fund_house(soup),
    ]

    sections: list[ParsedSection] = []
    for extractor in extractors:
        section = extractor()
        if section is not None:
            sections.append(section)

    found_types = {section.section_type for section in sections}
    missing = sorted(set(SECTION_TYPES) - found_types)
    if missing:
        logger.warning(
            "Missing sections for %s (%s): %s",
            scheme_name,
            source_url,
            ", ".join(missing),
        )

    if not sections:
        raise ValueError(f"No sections extracted for {scheme_name} ({source_url})")

    return sections
