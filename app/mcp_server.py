# ruff: noqa
import json
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("BookCompass")

# Simulated Book Database
BOOK_DATABASE = {
    "java": [
        {"title": "Head First Java", "author": "Kathy Sierra & Bert Bates", "difficulty": "Beginner", "reading_time": "15 Hours", "summary": "A brain-friendly guide to learning Java and object-oriented programming."},
        {"title": "Effective Java", "author": "Joshua Bloch", "difficulty": "Intermediate", "reading_time": "20 Hours", "summary": "Best practices and deep insights for writing robust, efficient Java code."},
        {"title": "Spring Start Here", "author": "Laurentiu Spilca", "difficulty": "Intermediate", "reading_time": "18 Hours", "summary": "A hands-on introduction to the Spring Framework and Spring Boot fundamentals."},
        {"title": "Spring in Action", "author": "Craig Walls", "difficulty": "Advanced", "reading_time": "25 Hours", "summary": "Comprehensive guide to building microservices and web apps with Spring."}
    ],
    "python": [
        {"title": "Python Crash Course", "author": "Eric Matthes", "difficulty": "Beginner", "reading_time": "12 Hours", "summary": "Fast-paced introduction to programming with Python, projects-based."},
        {"title": "Fluent Python", "author": "Luciano Ramalho", "difficulty": "Advanced", "reading_time": "30 Hours", "summary": "Deep dive into Python's features, idioms, and core mechanisms."},
        {"title": "Automate the Boring Stuff with Python", "author": "Al Sweigart", "difficulty": "Beginner", "reading_time": "10 Hours", "summary": "Practical programming for total beginners using Python to automate tasks."}
    ],
    "investing": [
        {"title": "The Intelligent Investor", "author": "Benjamin Graham", "difficulty": "Advanced", "reading_time": "25 Hours", "summary": "The classic text on value investing and market principles."},
        {"title": "The Little Book of Common Sense Investing", "author": "John C. Bogle", "difficulty": "Beginner", "reading_time": "8 Hours", "summary": "Simple, low-cost index fund investing advice from Vanguard's founder."},
        {"title": "A Random Walk Down Wall Street", "author": "Burton G. Malkiel", "difficulty": "Intermediate", "reading_time": "15 Hours", "summary": "A history and analysis of stock market pricing theories and strategies."}
    ],
    "communication": [
        {"title": "How to Win Friends and Influence People", "author": "Dale Carnegie", "difficulty": "Beginner", "reading_time": "10 Hours", "summary": "Core timeless principles of interpersonal communication and leadership."},
        {"title": "Crucial Conversations", "author": "Joseph Grenny", "difficulty": "Intermediate", "reading_time": "12 Hours", "summary": "Tools for talking when stakes are high and opinions vary."},
        {"title": "Never Split the Difference", "author": "Chris Voss", "difficulty": "Intermediate", "reading_time": "14 Hours", "summary": "Former FBI hostage negotiator's field-tested techniques for business negotiation."}
    ]
}

@mcp.tool()
def search_books_by_topic(topic: str) -> str:
    """Search for book recommendations in our curated database by topic.
    
    Args:
        topic: The topic/learning goal (e.g. 'java', 'python', 'investing', 'communication').
    """
    topic_clean = topic.lower().strip()
    results = []
    
    # Try finding exact or partial matches
    for key, books in BOOK_DATABASE.items():
        if key in topic_clean or topic_clean in key:
            results.extend(books)
            
    if not results:
        # Generic fallback books
        return json.dumps({
            "status": "partial_match",
            "message": f"No custom curated books found for '{topic}'. Showing default recommendations.",
            "books": [
                {"title": f"Introduction to {topic.title()}", "author": "Generic Expert", "difficulty": "Beginner", "reading_time": "12 Hours", "summary": f"Foundational guide to learning {topic}."},
                {"title": f"Mastering {topic.title()}", "author": "Generic Veteran", "difficulty": "Advanced", "reading_time": "24 Hours", "summary": f"Advanced techniques and deep concepts in {topic}."}
            ]
        }, indent=2)
        
    return json.dumps({"status": "success", "books": results}, indent=2)

@mcp.tool()
def get_book_details_by_title(title: str) -> str:
    """Fetch complete details, outline, and page count estimate for a book by title.
    
    Args:
        title: The exact or approximate title of the book.
    """
    title_clean = title.lower()
    for category, books in BOOK_DATABASE.items():
        for book in books:
            if title_clean in book["title"].lower():
                return json.dumps({
                    "title": book["title"],
                    "author": book["author"],
                    "difficulty": book["difficulty"],
                    "reading_time": book["reading_time"],
                    "summary": book["summary"],
                    "page_count_estimate": int(book["reading_time"].split()[0]) * 35  # estimate ~35 pages per hour
                }, indent=2)
                
    return json.dumps({"error": f"Book '{title}' not found in local database."}, indent=2)

@mcp.tool()
def calculate_reading_pace(total_hours: int, hours_per_week: int) -> str:
    """Calculate the estimated weeks and daily study target given total reading time and study capability.
    
    Args:
        total_hours: Total estimated reading hours.
        hours_per_week: Number of hours the user can study per week.
    """
    if hours_per_week <= 0:
        return json.dumps({"error": "Hours per week must be greater than zero."}, indent=2)
        
    weeks = total_hours / hours_per_week
    daily_target_minutes = (hours_per_week / 7) * 60
    
    return json.dumps({
        "total_reading_hours": total_hours,
        "weekly_study_commitment": f"{hours_per_week} Hours",
        "estimated_duration_weeks": round(weeks, 1),
        "daily_study_target": f"{round(daily_target_minutes)} minutes/day"
    }, indent=2)

if __name__ == "__main__":
    mcp.run()
