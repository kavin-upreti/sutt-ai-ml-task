import statistics
from datetime import datetime
from typing import Any, Dict, List

from .misc import clean_text


def structure_comments(comments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Return comments with the relevant information
    """

    structured_comments = []

    for comment in comments:
        if not isinstance(comment, dict):
            continue

        cleaned_text = clean_text(comment.get("text", ""))

        if comment.get("score", 0) < 0 or len(cleaned_text) < 10: 
            # this filtering is also shown in compute_audit_stats
            # we removed all comments with negative scores or length too less
            continue

        structured_comment = {
            "id": comment.get("id"),
            "text": cleaned_text,
            "upvotes": comment.get("score"), # stage 2 -> preserve upvotes
            "by": comment.get("by", "Unknown"),
            "position": comment.get("position", 0),
            "parent": comment.get("parent", 0), # stage 2 -> preserve parent
            "root_id": comment.get("root_id"),
            "time": datetime.fromtimestamp(comment.get("time")) # stage 2 -> preserve time
        } # all the relevant parameters are introduced, which are used by the AI or during the audit etc

        structured_comments.append(structured_comment)

    return structured_comments


def compute_audit_stats(raw_stories: List[Dict[str, Any]], raw_comments: List[Dict[str, Any]], structured_comments: List[Dict[str, Any]],) -> Dict[str, Any]:
    """
    Manually compute statistics of the data received from the API for the query 
    """

    total_stories_fetched = len(raw_stories)
    story_points = [story.get("points", 0) for story in raw_stories]
    story_comment_counts = [story.get("num_comments", 0) for story in raw_stories]

    total_raw_comments = len(raw_comments) # all comments -> story's comments, comments on story's comments etc
    # whereas structured comments are the ones we actually use 

    discarded_negative_score = 0
    discarded_too_short = 0

    # stage 1 -> compute the actual statistics
    for comment in raw_comments:
        if not isinstance(comment, dict):
            continue

        if comment.get("score", 0) < 0:
            discarded_negative_score += 1 # dont use comments with a bad score
            continue

        cleaned_text = clean_text(comment.get("text", "")) # better text

        if len(cleaned_text) < 10:
            discarded_too_short += 1 # dont use comments which are too short

    upvotes = [comment["upvotes"] for comment in structured_comments if comment.get("upvotes") is not None]
    text_lengths = [len(comment["text"]) for comment in structured_comments]

    return {
        "total_stories_fetched": total_stories_fetched,
        "avg_story_points": round(statistics.mean(story_points), 1) if story_points else 0,
        "avg_story_comments": round(statistics.mean(story_comment_counts), 1) if story_comment_counts else 0,
        "total_raw_comments": total_raw_comments,
        "total_kept_comments": len(structured_comments),
        "total_discarded_comments": total_raw_comments - len(structured_comments),
        "discarded_negative_score": discarded_negative_score,
        "discarded_too_short": discarded_too_short,
        "avg_upvotes": round(statistics.mean(upvotes), 1) if upvotes else None,
        "max_upvotes": max(upvotes) if upvotes else None,
        "avg_comment_length_chars": round(statistics.mean(text_lengths), 0) if text_lengths else 0,
    }
