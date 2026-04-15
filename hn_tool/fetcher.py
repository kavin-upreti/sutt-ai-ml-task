from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import requests


def fetch_item(cache: Dict[int, Dict[str, Any]], item_id: int) -> Optional[Dict[str, Any]]:
    """
    Get the data of the given item, be it a story or a comment, and store it in cache
    """

    if item_id in cache:
        return cache[item_id]

    try:
        url = f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
        response = requests.get(url)
        response.raise_for_status()

        item_data = response.json()
        cache[item_id] = item_data # store it in cache for future use
        return item_data
    except requests.RequestException as error:
        print(f"Error fetching item {item_id}: {error}")
        return None


def fetch_stories(query: str, max_stories: int) -> List[Dict[str, Any]]:
    """
    Get the relevant stories for the given query
    """

    try:
        formatted_query = query.replace(" ", "%20")
        url = f"https://hn.algolia.com/api/v1/search?query={formatted_query}&tags=story"

        # stage 1 -> get the actual data
        response = requests.get(url)
        response.raise_for_status() # raises HTTPError in case of fault

        data = response.json()
        stories = data.get("hits", []) # get all stories of the given query
        stories = sorted(stories,
            key=lambda story: (story.get("points", 0), story.get("num_comments", 0)),
            reverse=True) # sort stories according to relevance
        # higher points -> more relevant
        # higher comments -> relevant but not more than points

        print(f"Returning top {max_stories} out of the {len(stories)} found stories for query: {query}")
        return stories[:max_stories]
    except requests.RequestException as error:
        print(f"Error fetching stories: {error}")
        return []


def fetch_comments_of_comment(cache: Dict[int, Dict[str, Any]], comment_id: int, depth: int) -> List[Dict[str, Any]]:
    """
    Get all the comments of the given comment, and introduce the position of the comment 
    Position 0 signifies a reply to the story, position 1 is a reply to a comment and so on
    """

    # stage 2 -> preserve thread depth
    comment = fetch_item(cache, comment_id)

    if not comment or comment.get("deleted") or comment.get("dead"):
        return []

    comment["position"] = depth

    if depth > 3 or "kids" not in comment:
        return [comment] # no need to go too far into the comment tree

    results = [comment]

    for child_comment_id in comment["kids"]:
        results.extend(fetch_comments_of_comment(cache=cache, comment_id=child_comment_id, depth=depth + 1))

    return results


def fetch_comments_for_story(cache: Dict[int, Dict[str, Any]], story_id: int) -> List[Dict[str, Any]]:
    """
    Get all comments of a given story
    """

    story = fetch_item(cache, story_id)

    if not story:
        print(f"Could not fetch story {story_id}")
        return []

    title = story.get("title", "No title provided")
    show_title = title if len(title) <= 50 else title[:50] + "..."

    if "kids" not in story:
        print(f"Fetched 0 comments for story {story_id} (title: {show_title})")
        return []

    comment_ids = story["kids"] # all comment ids for the story
    comments = []

    print(f"\n\tFetching comments for story {story_id}")
    # the snippet below is written by AI, since my method was awfully slow and I did not know a workaround
    with ThreadPoolExecutor(max_workers=10) as executor:
        # basically only 10 executions max at once can happen
        # stage 1 -> get the actual data
        future_to_id = {
            executor.submit( # we pass the function and its parameters to the executor, which returns a Future object
                fetch_comments_of_comment,
                cache=cache,
                comment_id=comment_id,
                depth=0
            ): comment_id for comment_id in comment_ids
        }
        # we had this reverse mapping done as we need to know which comment the future result pertains to
        # as in, if we had 
        # comment_id: Future object
        # then we could get the result with future.result(), but we would have to iterate through the dict to know the comment_id
        # in this way we can just do future_to_id[future object] and get the comment_id

        for future in as_completed(future_to_id): # as_completed returns the objects in the order they finished
            comment_id = future_to_id[future]
            try:
                comment_list = future.result() # returns the result that the executor got
                comments.extend(comment_list)
            except Exception as error:
                print(f"Error fetching comment {comment_id}: {error}")

    print(f"Fetched {len(comments)} comments for story {story_id} (title: {show_title})")
    return comments