from typing import Any, Dict, List
from groq import Groq

from .config import load_api_key
from .fetcher import fetch_comments_for_story, fetch_stories
from .processor import compute_audit_stats, structure_comments
from .llm import build_context, chat_with_data, generate_audit, generate_digest, summarize_old_messages


class HNIntelligenceTool:
    def __init__(self) -> None:
        self.cache: Dict[int, Dict[str, Any]] = {} # {story_id/comment_id: {"key": value}, ..}
        self.client = Groq(api_key=load_api_key())

    def start_chat_interface(self, query, digest, structured_comments: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """
        Let the user ask further questions using information provided in the generated digest
        """

        # stage 4 -> sliding window logic combined with summarizing older messages. keeps 4 messages
        print("\nYou can now ask questions about this discussion. Type 'exit' or 'quit' to quit.")

        chat_history: List[Dict[str, str]] = [] # looks like [{"role": "user/assistant", "content": "..."}]
        conversation_summary = ""

        while True:
            question = input("\nEnter your question: ")
            if question.lower() in ["exit", "quit"]:
                break

            chat_history.append({"role": "user", "content": question})

            context = build_context(query=query, digest=digest, comments=structured_comments, chat_history=chat_history, conversation_summary=conversation_summary)
            # give some context to the AI on what has happened so far, to avoid giving the raw conversation and data forever

            answer = chat_with_data(self.client, question, context)
            print(f"\nAnswer: {answer}")

            chat_history.append({"role": "assistant", "content": answer})

            if len(chat_history) > 8:
                conversation_summary = summarize_old_messages(self.client, chat_history[:-4])
                # Stage 4 -> content from more than 4 messages ago (2 interactions) is summarized
                chat_history = chat_history[-4:] # while recent 4 messages (2 interactions) are shown exactly as they were

        return chat_history

    def run(self, query, max_stories = 5) -> None:
        """
        Run the program
        """

        print(f"Searching Hacker News for: {query}")

        stories = fetch_stories(query, max_stories = max_stories)
        if not stories:
            print("No stories found.")
            return

        all_comments: List[Dict[str, Any]] = [] # key value pair, key is a string, value can be any data type

        for story in stories:
            comments = fetch_comments_for_story(self.cache, story["story_id"]) # get all comments of the given story
            all_comments.extend(comments)

        if not all_comments:
            print("No comments found.")
            return

        structured_comments = structure_comments(all_comments) # remake comments with relevant parameters
        structured_comments.sort(
            key=lambda c: (c["root_id"], c["parent"], c["position"], (-c["upvotes"] if isinstance(c["upvotes"], int) else 0))
        ) 
        # stage 2 -> so that thread context is preserved
        # sort them so that all comments of similar story's id are together, then those of the similar parent comment id are together, then those of lower position are first, and at last those with more upvotes are first

        # Stage 1 of program -> generate audit
        stats = compute_audit_stats(stories, all_comments, structured_comments)  # get statistics of the stories and comments
        audit = generate_audit(self.client, query, stats) # pass the statistics to an AI for generating a strictly relevant audit

        print("\n" + "-" * 80)
        print("DATA AUDIT")
        print("-" * 80)
        print(audit) # give the audit

        digest = generate_digest(self.client, query, stories, structured_comments) 
        # show the news in a digest form - all the relevant information considered and shown in a comfortable way

        print("\n" + "-" * 80)
        print("HACKER NEWS INTELLIGENCE DIGEST")
        print("-" * 80)
        print(digest)

        self.start_chat_interface(query, digest, structured_comments)
