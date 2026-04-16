# HN Thread Intelligence Tool
📰 This is a tool that fetches **live news** from the <ins>Hacker News API</ins> on any topic and generates a structured digest for the same.<br>
💬 It also lets you **chat with an AI** regarding the data to learn more. It behaves as a **research assistant** that reads the thread for the ease of the user.

**Setup**
1. Clone the repository
2. Install the dependencies:
```bash
pip install -r requirements.txt
```
3. Create a `.env` file in the root directory itself and add your Groq API key in this manner:
```
GROQ_API_KEY = your_key
```
4. Run the tool:
```py
python main.py
```

You will have to enter a topic of interest and the number of stories to consider for your digest (default max, maximum 10)

---

## 👷🏽 How it works

### 📊 Stage 1: Data Acquisition & Audit

The data is fetched is received from two APIs:
- **HN Algolia Search API**: helps find relevant stories for the given query
- **HN Firebase API**: helps fetch individual items (stories and comments)

The stories returned for the digest are sorted in order of relevance where points come first and number of comments second, so that the most lively and engaging discussions are used.

Instead of asking the LLM of the AI (Groq) to guess the data quality, real time statistics are computed in the code (function `compute_audit_stats()` in file `processor.py`).<br>Things like total number of raw comments fetched, how many comments were discarded (why?), average upvotes, average comment length, and date range are passed onto the LLM, which writes the data in the form of an audit and is strictly bound by the actual data fetched.

**What gets discarded and why:**
- Comments with a negative score: these have been downvoted by the people and are highly unlikely to contain useful information
- Comments which are very short post refining of the raw text are usually acknowledgements or jokes with no fruit

---

### 🌲 Stage 2: Chunking & Structure

HN threads are trees. Many comments have replies to them as well. The approach of splitting by token count (a token is roughly 4 words) destroys conversation's context. A reply loses meaning when separated from what it was replying to. Hence, this approach was discarded.<br>Instead, we implemented:

**Recursive fetching with comment depth tracking** (function `fetch_comments_of_comment()` in file `fetcher.py`): Instead of only fetching top-level comments, each comment's replies are fetched recursively. A `position` field is attached to each comment at fetch time, where `0` is assigned for direct replies to the story, `1` is assigned for replies to those replies, and so on. When the depth exceeds `3`, we stop fetching further comments in order to avoid extremely long  threads which usually go off the topic, and to also keep API calls manageable (since excessive length will be tough to handle).

**Preserving context**: Each comment has a `parent` field from the API itself, which is the id of the comment or the story it directly replied to, and a `root_id` field manually introduced, which is the id of the story it belongs to. After structuring the comment according to our needs, the comments are sorted with relevance in the order `(root_id, parent, position, upvotes)` so that the replies to a comment near the story's comments. Root ID (which is the story's ID) being first implies that all comments with same root ID are grouped together, then all of the same parent ID (the one they are directly replying to) rather than being scattered. This builds a reasonable thread order and is easy for the AI to interpret.

**Threading**: Top comments are fetched in parallel (maximum 10) using `ThreadPoolExecutor` so that the performance is better.

**Selecting comments for the digest**: The function `get_best_comments()` in file `misc.py` sorts the comments by upvotes first and depth second, since more upvoted comments tend to be the important ones while deeper replies can steer out of the conversation and be irrelevant.

---

### 📰 Stage 3: Generating the Digest

The digest is generated in the function `generate_digest()` in file `llm.py`. The top 100 comments by relevance are selected and formatted with indentation to show their depth so that LLM can see the conversational structure, which looks something like:

```
[Position 0] Comment (7 upvotes):
    Main argument here

    [Position 1] Comment (3 upvotes):
        Reply to main argument
```

The LLM is strictly instructed to gather the actual information, such as the main arguments, pros, cons, alternatives (if any), and the consensus of the discussion, rather than producing a rough summary. The digest has six sections: overview of the story, arguments for the story, arguments against the story, alternative tools mentioned, consensus (if any), and miscellaneous details that could be useful.

---

### 💬 Stage 4: Context Management for Chat

Fitting the entire digest, complete chat history and all raw comments into the LLM context window forever is not optimal. The strategy used here is a **sliding window combined with summarization**:

- The most recent 4 messages (2 exchanges) are kept exactly as they are for accurate immediate context
- Everything older than that is summarized into a short paragraph of max 3 lines by the LLM (function `summarize_old_messages()` in file `llm.py`)
- Everytime the user chats, the LLM receives the complete digest, the conversation summary, the exact recent messages, and the top 5 comments for reference

This ensures that the LLM always has precise information of the recent conversation without destroying the older context entirely.

---

### 🛡️ Stage 5: Edge Cases

All four given edge cases are mainly handled through the prompt in function `chat_with_data()` in file `llm.py`:

A. **A question that has no answer in the fetched data.**: The prompt strictly instructs the LLM to state that it does not have enough information from the fetched discussion instead of giving outside knowledge<br>
B. **Contradictory opinions in the data**: The prompt explicitly tells the LLM to present both sides from a neutral perspective when the discussion as conflicting views instead of settling on one of them.<br>
C. **A question that references something from way earlier in the chat**: This is partially handled by the summarization strategy implemented in stage 4 - if a message was summarized, the exact wording is not recoverable due to LLM restraints (not going overboard with the prompt length etc), but the key information is preserved in the summary. This is a standard limitation that is hit but was the best solution I could implement.<br>
D. **A manipulative question designed to make the bot agree with a false consensus**: The prompt instructs the LLM not to validate what is asked in the question, and to only report what the fetched discussion actually says in the form of opinions. Bounding the responses to be strictly from within the fetched data is the method used to not get swayed away.

---

## 🤖 AI Usage for making the tool

- AI was used to help write parts of this code, such as `ThreadPoolExecutor` block in `fetch_comments_for_story()` was implemented by an AI due to having lack of knowledge on how to send multiple requests simultaneously. The standard approach that would have been implemented would have been using a loop through the comment IDs and fetching it one by one, which would be excruciatingly slow.
- The regex for converting HTML links to plain text in the function `clean_text()` was by an AI too due to lack of knowledge on using regex at that level.
- The code was refined and reviewed by an AI to find out what things were missing and any logical errors that may have occured in the program
