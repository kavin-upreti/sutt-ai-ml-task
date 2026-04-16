from hn_tool import HNIntelligenceTool

if __name__ == "__main__":
    tool = HNIntelligenceTool()
    query = input("Enter the topic you want to search about (eg: SQLite in production): ")
    max_stories = input("How many stories do you want to be considered? (hit enter or a non integer for 5, max 10): ")
    try:
        max_stories = int(max_stories)
        max_stories = min(10, max_stories)
    except Exception as E:
        max_stories = 5
    if query == "":
        query = "SQLite in production"
    tool.run(query, max_stories)
