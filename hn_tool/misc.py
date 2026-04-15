import re
from typing import Any, Dict, List


def clean_text(text: str) -> str:
    """
    Get text which is actually relevant instead of everything given in the comment text
    """

    if not text:
        return ""

    replacements = [
        (r"<p>", "\n\n"),
        (r"<br>", "\n"),
        (r"<br/>", "\n"),
        (r'<a href="([^"]+)"[^>]*>([^<]+)</a>', r"\2 (\1)"), # replace links in the form of "text (url)"
        # this last sub was done by an ai since i had no clue how to do it
    ] # this is for all tags that needed any changes in the formatting due to the text
    # <i>, <b> etc wont really be useful so we just remove them with the others later

    cleaned_text = text

    for pattern, replacement in replacements:
        cleaned_text = re.sub(pattern, replacement, cleaned_text, flags=re.IGNORECASE)

    cleaned_text = re.sub(r"<[^>]+>", "", cleaned_text) # remove all other HTML tags
    cleaned_text = re.sub(r"\n\s*\n", "\n\n", cleaned_text) # remove multiple new lines
    return cleaned_text


def get_best_comments(comments: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    """
    Sort comments according to relevance, giving upvotes the higher priority than depth
    """

    eligible = [comment for comment in comments if comment.get("text")]

    return sorted(
        eligible, 
        key=lambda com: (com.get("upvotes") if isinstance(com.get("upvotes"), int) else 0, -com.get("position", 0)),
        reverse=True)[:limit] 
    # too many comments, so we sort them according to relevance, first by upvotes and then by position
    # lower position = more relevant, so we added a - (since we are using reverse sorting so descending, and so 0 > -1 > -2..)