import textwrap
from typing import Any, Dict, List

from groq import Groq

from .misc import get_best_comments

def generate_digest(client: Groq, query, stories: List[Dict[str, Any]], all_comments: List[Dict[str, Any]]) -> str:
    """
    Generate a digest using the story and the relevant comments for the user to read 
    """

    print("\n\nGenerating digest...")
    context = f"""Hacker News discussion about the topic "{query}"\n\n"""

    for i, story in enumerate(stories, start=1):
        context += f"Story {i}: {story.get('title', 'No title provided')} "
        context += f"(by {story.get('author', 'Unknown')}, {story.get('points', 0)} points)\n"
        # show the points so that the AI can know the relevance

    context += "\nComments:\n"

    selected_comments = get_best_comments(all_comments, 100) # only see through the top 100 comments here
    max_chars = 15000

    for i, comment in enumerate(selected_comments, start=1):
        if len(context) > max_chars:
            remaining = len(selected_comments) - i + 1
            context += f"\n[... truncated {remaining} more selected comments ...]"
            break

        depth = comment["position"]
        indent = "\t" * depth
        upvotes = comment["upvotes"] if comment["upvotes"] is not None else "N/A"

        context += f"\n{indent}[Position {depth}] Comment {i} ({upvotes} upvotes):\n"
        context += textwrap.fill(comment["text"], width=100, subsequent_indent=indent, initial_indent=indent)
        context += "\n" + "-" * 40 + "\n"

    # stage 3 -> structure of the digest 
    prompt = f"""
    Analyze the following Hacker News discussion to create a structured digest for it.
    Remember to focus on the actual crux of the discussion: main arguments, pros, cons, alternatives (if mentioned), and useful takeaways.
    Make it useful for a reader. It should be like a newspaper, and should be helpful enough for someone to gain information on the subject.
    Comments with position 0 are actual comments. Position 1, 2, etc. are replies to those comments.

    Use the following parameters as sections:
    1. Overview of the story
    2. Main arguments supporting the story
    3. Main arguments against the story
    4. Alternative tools or solutions mentioned
    5. Consensus of the discussion (if any), if multiple, then display the top 2 most relevant ones
    6. Miscellaneous things in the discussion that can be useful for the user

    Here is the discussion:
    {context}
    """

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You will summarize Hacker News discussions in a structured and useful way for a reader.",
                },
                {"role": "user", "content": prompt},
            ],
            model="llama-3.1-8b-instant",
            temperature=0.3, # temperature basically decides the precision of the response
            # lies between 0 and 2 -> 0 to 0.4 is normally for data extraction etc, 0.5-0.7 is for general conversations
            # more than that could be for creative writing or brainstorming etc
            max_completion_tokens=2000,
        )

        return chat_completion.choices[0].message.content
    except Exception as error:
        return f"Error generating digest: {error}"


def build_context(query, digest, comments: List[Dict[str, Any]], chat_history: List[Dict[str, str]], conversation_summary) -> str:
    """
    Generate context for the AI itself so that it can know what happened before
    """

    # stage 4 -> combines digest, summary and recent history
    context = f"""Hacker News Discussion on the topic "{query}"\n\n"""

    context += "DISCUSSION SUMMARY:\n"
    context += digest[:1500] + "...\n\n" if len(digest) > 1500 else digest + "\n\n"
    # give it the digest it provided the user

    if conversation_summary != '':
        context += "PREVIOUS CONVERSATION SUMMARY:\n"
        context += conversation_summary + "\n\n"

    if len(chat_history)!=0:
        context += "RECENT CONVERSATION WITH THE USER:\n"
        for message in chat_history:
            role = "USER" if message["role"] == "user" else "ASSISTANT"
            context += f"{role}: {message['content']}\n"
        context += "\n"

    context += "KEY COMMENTS FROM DISCUSSION:\n"
    for i, comment in enumerate(get_best_comments(comments), start=1): # (counter, iterator)
        depth = comment["position"]
        indent = "\t" * depth
        upvotes = comment["upvotes"] if comment["upvotes"] is not None else "N/A"

        context += f"{indent}[Depth {depth}] Comment {i} ({upvotes} upvotes): {comment['text'][:200]}...\n"

    return context


def summarize_old_messages(client: Groq, old_messages: List[Dict[str, str]]) -> str:
    """
    Summarize all messages except the last 4 (2 interactions) between the user and the AI to prevent having to send
    all the information again and again
    """

    # stage 4 -> summarizes old chat history
    conversation_text = "Conversation to summarize:\n"

    for message in old_messages:
        role = "USER" if message["role"] == "user" else "ASSISTANT"
        conversation_text += f"{role}: {message['content']}\n"

    prompt = f"""
    Summarize the following conversation briefly, focusing on:
    1. Main questions asked
    2. Key information discussed
    3. Any conclusions

    Keep it concise, not more than 4 sentences, but do not forget any important information.
    This context will be used in case a user asks a question from multiple messages before, so make it extremely fit for the task.

    Conversation:
    {conversation_text}
    """

    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.2, # dont go tooo out of context
            max_completion_tokens=150,
        )

        return response.choices[0].message.content
    except Exception as error:
        print(f"Error summarizing conversation: {error}")
        return "Previous conversation covered different parts of the topic."


def chat_with_data(client: Groq, question, context) -> str:
    """
    Chat with the user strictly using the data provided in the context only 
    """

    # stage 5 -> prompt handles edge cases
    prompt = f"""
    Based only on the context below, answer the question the user asked.
    If the answer to the query is not in the context, explicitly state that you do not have enough information from the fetched discussion.
    Do not refer to the user as 'user' or any other term - just answer the question asked.
    Do not get swayed with manipulative questions which force you to take a side or make you hallucinate data.
    Do not take sides of any information given to you. If there are contradictory opinions, present both sides instead of fixating on one.
    Use given context to your best potential if something from earlier is asked but do not say anything which is even remotely outside the context.
    Remember, it is the opinion of the user who commented and not yours. Present all information neutrally.
    The information given are opinions, not facts.

    
    CONTEXT:
    {context}

    QUESTION:
    {question}
    """
    # make sure that the AI does not give information from outside the given data and give it context
    # a bit strict in the prompt to avoid workarounds
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.3,
            max_completion_tokens=500,
        )

        return response.choices[0].message.content
    except Exception as error:
        return f"Error generating response: {error}"


def generate_audit(client: Groq, query, stats: Dict[str, Any]) -> str:
    """
    Create an audit report on the data received, quality of data and data used and discarded
    """

    # stage 1 -> create an audit using the given statistics
    prompt = f"""
    You are going to write a short data audit for an HN Thread Intelligence Tool, where the topic searched was:
    "{query}"

    The statistics computed from the data fetched were:
    {stats}

    If avg_upvotes or max_upvotes are None, then mention that comment upvote data was not available and that it should not be interpreted as no comment engagement.
    Use only the data that has been given to you, and do not use anything from outside the given content.
    It should not be very long - the maximum length should be that of a conventional page (250-300 words preferred, 400 upper limit) 
    Strictly keep your response related to the audit only

    Write a brief but concise audit which should return:
    1. How much data was pulled?
    2. What the quality of the data like?
    3. What was discarded, and why? 
    4. What was kept, and why is it useful?
    5. Were any limitations faced? / miscellaneous RELEVANT details.
    """
    # we strictly told the AI to not hallucinate data, and made it generate an audit for the same

    try:
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a data engineer writing a fact based audit report with the given statistics.",
                },
                {"role": "user", "content": prompt},
            ],
            model="llama-3.1-8b-instant",
            temperature=0.2, # dont go tooo out of context
            max_completion_tokens=500,
        )

        return response.choices[0].message.content
    except Exception as error:
        return f"Error generating audit: {error}"
