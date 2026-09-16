import re


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


# Phrases that clearly come from a RECRUITER/COMPANY advertising an opening.
HIRE_CUES = [
    r"we\s*'?re?\s+hiring",
    r"we\s+are\s+hiring",
    r"we\s*'?re?\s+looking\s+for",
    r"we\s+are\s+looking\s+for",
    r"we\s+are\s+seeking",
    r"we\s*'?re?\s+seeking",
    r"immediate\s+hiring",
    r"#hiring",
    r"#wearehiring",
    r"apply\s+now",
    r"apply\s*:",
    r"send\s+(?:your\s+)?resume",
    r"share\s+(?:your\s+)?resume",
    r"job\s+description",
    r"job\s+title",
    r"key\s+responsibilities",
    r"responsibilities\s*:",
    r"required\s+skills\s*:",
    r"qualifications\s*:",
    r"join\s+our\s+team",
    r"we\s+are\s+seeking\s+a",
    r"hiring\s+(?:a\s+|an\s+)?(?:full\s*stack|mern|frontend|backend|software|python|react|node)",
    r"position\s*:",
    r"location\s*:",
    r"salary\s*:",
    r"why\s+join",
    r"hr\s*|talent\s+acquisition|recruit\w*",
]

# Phrases typical of an individual marketing HIMSELF for a job (job seeker).
SEEK_CUES = [
    r"open\s+to\s+work",
    r"#?opentowork",
    r"#referralsappreciated",
    r"repost\s*(?:or|and|,)?\s*referral",
    r"referral\s*(?:or|and|,)?\s*repost",
    r"(?:repost|referral)s?\s*(?:would|will|really)?\s*mean\s*a\s*lot",
    r"hello\s+everyone",
    r"hi\s+(?:everyone|all|connections|recruiters|linkedin)",
    r"i\s*'?m?\s+(?:excited|happy|thrilled)\s+to\s+share",
    r"(?:i|i'?m)\s+am?\s+(?:a\s+)?\w+\s+developer",
    r"my\s+journey\s+so\s+far",
    r"i\s+am\s+looking\s+for",
    r"i\s*'?m\s+looking\s+for",
    r"looking\s+for\s+(?:a|an|new)\s+(?:full\s*stack|mern|frontend|backend|software)\s+(?:developer|role|position|job)",
    r"looking\s+for\s+(?:new\s+)?(?:opportunit\w*|role|job)s?",
    r"open\s+(?:to|for)\s+(?:new\s+)?(?:opportunit\w*|role|job)s?",
    r"available\s+for\s+(?:full\s*time|remote|contract|a\s+role)",
    r"willing\s+to\s+relocate",
    r"please\s+share\s+this\s+post",
    r"help\s+me\s+(?:find|get|secure)",
    r"connect\s+with\s+me",
    r"reach\s+(?:out|me)\s+(?:to\s+)?(?:me\s+)?at",
    r"i\s+would\s+love\s+to\s+(?:join|work)",
    r"(?:a\s+)?repost\s+(?:would|will)\s+mean",
    r"seriously\s+looking\s+for",
]


def is_job_seeker_post(content: str) -> bool:
    """Return True if the post is an individual promoting HIMSELF for a job
    (open-to-work / seeking referrals / hi everyone) instead of a recruiter
    advertising an actual opening.

    Decision rule:
    - If strong recruiter cues (WE ARE HIRING, Apply Now, responsibilities, salary, ...)
      are present, treat as a real job post (not a seeker) even if a few seek cues
      leak in (e.g. "We're looking for someone willing to relocate").
    - Otherwise, strong seeker cues mark it as a job-seeker post to be skipped.
    """
    if not content:
        return False
    low = _norm(content)

    hire_hits = sum(1 for pat in HIRE_CUES if re.search(pat, low))
    if hire_hits >= 2:
        return False

    seek_hits = sum(1 for pat in SEEK_CUES if re.search(pat, low))
    if hire_hits == 1 and seek_hits >= 2:
        return True
    if hire_hits == 0 and seek_hits >= 1:
        return True
    return False