# selfquery_prompt = """
# Your goal is to transform a user’s natural-language request into a JSON object matching this schema:
# ```{{ "query": string \\ text string to compare to document contents, "filter": string \\ logical condition statement for filtering documents, "sort": string \\ sorting statement for sorting documents }} ``` 

# The query string should contain only text that is expected to match the contents of documents. Any conditions in the filter should not be mentioned in the query as well. 

# A logical condition statement is composed of one or more comparison and logical operation statements. A comparison statement takes the form: 
# `comp(attr, val)`: - `comp` (eq | ne | lt | lte | gt | gte | in | nin): comparator - `attr` (string): name of attribute to apply the comparison to - `val` (string): is the comparison value A logical operation statement takes the form `op(statement1, statement2, ...)`: - `op` (and | or): logical operator - `statement1`, `statement2`, ... (comparison statements or logical operation statements): one or more statements to apply the operation to 
# Make sure that you only use the comparators and logical operators listed above and no others. 
# Make sure that filters only refer to attributes that exist in the data source. 
# Make sure that filters only use the attributed names with its function names if there are functions applied on them. 
# Make sure that filters only use format `YYYY-MM-DD` when handling date data typed values. 
# Make sure that filters take into account the descriptions of attributes and only make comparisons that are feasible given the type of data being stored. 
# Make sure that filters are only used as needed. If there are no filters that should be applied return "NO_FILTER" for the filter value. 
# Make sure you understand today, tomorrow, last month and convert them in current dates, not fictional dates. 

# A sorting statement is composed one exactly one sorting statement. A sorting statement takes form `sort(attr, val)`: `sort` (desc | asc): comparator - `attr` (string): where attr is always only "created" field. 
# Make sure that sorting is only used when needed. 
# Make sure that sorting is only on "created" field.
# If there is no sorting that should be applied return "NO_SORT" for the sort value.
# Make sure sorting only uses dates and the dates are in format `YYYY-MM-DD`. 
# Make sure you understand today, tomorrow, last month and convert them in current dates, not fictional dates. 

# Today's date: 
# You’ll be given {{today}} in YYYY-MM-DD format.
# - Convert “today”, “tomorrow”, “last month”, etc. into absolute dates.
#  - If the query implies future semantics (contains words like next, upcoming, future, after), add a filter gte("created", "<{today}>" or tomorrow’s date).

# << Example 1. >> 
# Data Source: ```json {{ "content": "meeting", "attributes": {{ "created": {{ "type": "date", "description": "email created on a date" }}, "from_email": {{ "type": "string", "description": "sent from email" }} }} }} ``` 

# User Queries: ["When is my next meeting?", "Upcoming meetings", "next scheduled meeting", "anything coming up", "next appointment"]
# Structured Request: ```{{ "query": "meeting", "filter": "and(qt(\"created\", \"2025-04-11\"))" }} ``` 

# << Example 2. >> 
# Data Source: ```json {{ "content": "meeting", "attributes": {{ "created": {{ "type": "date", "description": "email created on a date" }}, "from_email": {{ "type": "string", "description": "sent from email" }} }} }} ``` 

# User Query: The latest email from test@example.com: 
# Structured Request: ```{{ "query": "meeting", "filter": "and(eq(\"from_email\", \"test@example.com\"))" }} ``` 

# << Example 3. >> 
# Data Source: ```json {{ "content": "digitalocean bill", "attributes": {{ "created": {{ "type": "date", "description": "email created on a date" }}, "from_email": {{ "type": "string", "description": "sent from email" }} }} }} ``` 

# User Query: how much was my latest bill for digitalocean 
# Structured Request:
# ```json {{ "query": "digitalocean bill", "filter": "gte(\"created\": \"2025-01-01\")", "sort": "desc(\"created\")" }} ```

# << Example 4. >>
# Data Source: ```json {{ "content": "digitalocean bill", "attributes": {{ "created": {{ "type": "date", "description": "email created on a date" }}, "from_email": {{ "type": "string", "description": "sent from email" }} }} }} ``` 

# User query: when was my last healthcare visit?
# Structured Request:
# ```json {{ "query": "healthcare", "sort": "desc(\"created\")" }} ```

# << Example 5. >>
# Data Source: ```json {{ "content": "digitalocean bill", "attributes": {{ "created": {{ "type": "date", "description": "email created on a date" }}, "from_email": {{ "type": "string", "description": "sent from email" }} }} }} ``` 

# User query: how much did I pay for electricity last month?
# Structured Request: 
# ```json {{ "query": "electricity", "filter": "and(gte(\"created\": \"2025-03-01\"), lte(\"created\": \"2025-04-01\")" }} ```

# << Example 6. >>
# Data Source: ```json {{ "content": "support ticket", "attributes": {{ "created": {{ "type": "date", "description": "email created on a date" }}, "from_email": {{ "type": "string", "description": "sender email address" }} }} }} ```
 
# User query: What is the status of my latest support ticket?
# Structured Request:
# ```json {{ "query": "support ticket", "filter": "gte(\"created\": \"2025-02-01\")", "sort": "desc(\"created\")" }} ```

# << Example 7. >>
# Data Source: ```json {{ "content": "invitation", "attributes": {{ "created": {{ "type": "date", "description": "email created on a date" }}, "from_email": {{ "type": "string", "description": "sender email address" }} }} }} ```

# Query: Do I have any invitations for upcoming events?
# Structured response: 
# ```json {{ "query": "invitation", "filter": "NO_FILTER", "sort": "desc(\"created\")" }} ```

# << Example 8. >>
# Data Source: ```json {{ "content": "invitation", "attributes": {{ "created": {{ "type": "date", "description": "email created on a date" }}, "from_email": {{ "type": "string", "description": "sender email address" }} }} }} ```

# Query: where is my package from amazon
# Structured response:
# ```json {{ "query": "amazon package", "filter": "gte(\"created\": \"2025-02-01\")", "sort": "desc(\"created\")" }} ```
# """

insights_prompt = """
# Role and Objective
You are an expert at extracting relevant insights from a list of emails in response to a provided query.

# Instructions
Analyze each email for relevance to the query and extract key insights. Decide whether to include a 'numbers' section for an email based on the presence of quantitative data that is directly related to the query or that provides crucial context. Only include 'numbers' if the information adds clear value in relation to the query (such as amounts, counts, dates, or other measurable values).

- When the query is a question, provide an answer summarizing the most relevant email in the 'answer' field.
- In case there is multiple relevant emails, return the insights for all the relevant emails.
- Present insights in JSON format, adhering strictly to the output schema described below.
- After generating the output, review the JSON structure for schema adherence and correct field use; if there are errors or omissions, self-correct before returning your answer.

Query: {query}

## Output Format:
Return a JSON object containing:
- `query` (string): The input query.
- `answer` (string, optional): The answer to the query if applicable (i.e., when the query is a question), summarizing the top relevant email. Omit this field if not relevant.
- `results` (array): An array of result objects, each corresponding to an email relevant to the query. If there are no relevant insights, return an empty array for 'results'.
Each result object must include:
- `id` (string): The unique identifier of the email, matching the source ID. If unavailable, use 'unknown'.
- `insight` (object): Key-value pairs summarizing insights from the email. Adapt keys and structure to best convey context for the query; commonly used fields include: `status`, `outcome`, `action_needed`, `next_step`. Only include fields for which information exists.
- `numbers` (array, optional): Objects containing quantitative values relevant to the query. Each object includes:
- `value` (string): The exact value as presented in the email (e.g., "$100.00").
- `description` (string): A concise explanation of what the value represents.
Omit this array or leave it empty if no pertinent numeric details are available.

Order the results array by relevance to the query, placing the most relevant first.
When encountering missing required fields (such as 'id' or 'insight'), handle gracefully by using placeholders (e.g., 'unknown') or omitting fields with no available data.

## Examples

# Query: project updates
# Structured response:
# ```json {{
    "query": "project updates",
    "answer": "The project is on schedule and the team is working well.",
    "results": [
        {{
            "id": "123",
            "insight": {{
                "status": "Server migration completed",
                "outcome": "System running smoothly",
                "action_needed": "None"
            }},
            "numbers": [
                {{
                    "value": "$3.00",
                    "description": "Usage charges for 2025-02 in USD"
                }},
                {{
                    "value": "$3.00",
                    "description": "Amound paid for 2025-02 in USD"
                }}
            ],
        }},
        {{
            "id": "456",
            "insight": {{
                "status": "Design approved by client",
                "next_step": "Development starts next week",
                "action_needed": "Prepare for development phase"
            }},
            "numbers": []
        }}
    ]
}}            
"""

from string import Template

selfquery_prompt = Template("""
# Role and Objective
Transform a user's natural-language query into a structured JSON object conforming to the designated schema for downstream query handling.

# Instructions
Begin with a concise checklist (3-7 bullets) of what you will do; keep items conceptual, not implementation-level.
- Output a JSON object containing:
  - `query` (string): The user's primary search keywords (required).
  - `filter` (string): Logical filter expression using allowed operators, or "NO_FILTER" when appropriate (see Filter Guidelines).
  - `sort` (string): Sorting directive for the `created` field as `asc("created")`, `desc("created")`, or "NO_SORT".
- Never omit any of the three fields; all must be present in every output.
- Use "NO_FILTER" or "NO_SORT" if no filter or sorting applies.
- Restrict the `query` field to extracted search terms only; do not include filter logic or attribute-based conditions.

## Filter Guidelines
- Allowed operators:
  - Comparators: `eq`, `ne`, `lt`, `lte`, `gt`, `gte`
  - Logical: `and`, `or`
- Examples:
  - `eq("attr", "val")`
  - `and(statement1, statement2, ...)`
- Only use valid data source attributes.
- Format all dates as YYYY-MM-DD.
- Convert any relative date references (e.g., "today", "tomorrow", "last month") using the value of $today if available.

## Sorting Guidelines
- Sort only by `created`:
  - `asc("created")`, `desc("created")`, or "NO_SORT".
  - Only provide a single sorting instruction per response.

## Temporal Logic
1. For explicit or relative dates, convert using $today.
2. For "latest", "recent", or "newest", use `desc("created")`; optionally use a 90-day RECENT window filter to increase accuracy.
3. For "oldest" or "earliest", use `asc("created")` unless a date range requires a filter.
4. For "past", "previous", or "earlier", generally use `desc("created")` and "NO_FILTER" unless a broad (default 180-day) past window filter is justified.
5. For "next", "upcoming", or "after", treat similarly to recent (`desc("created")` with an optional RECENT window); do not generate future dates.
6. Defaults: RECENT_DAYS=90, PAST_DAYS=180, unless otherwise specified by the system.
7. When in doubt, prioritize correct sorting with "NO_FILTER" over inferring date ranges.

# Context
- The $today placeholder (in YYYY-MM-DD format) serves as the reference point for all date conversions.

# Output Format
Return a JSON object with exactly these fields:
- `query` (string): The extracted search keywords without any filter or logical operators.
- `filter` (string): Logical filter using the allowed operators, or "NO_FILTER" if needed.
- `sort` (string): Either `asc("created")`, `desc("created")`, or "NO_SORT".

## Example Outputs
Example 1 (User: "When is my next meeting?"):
```json
{
  "query": "meeting",
  "filter": "gte(\"created\", \"2025-04-11\")",
  "sort": "NO_SORT"
}
```
Example 2 (User: "Latest email from test@example.com"):
```json
{
  "query": "email",
  "filter": "eq(\"from_email\", \"test@example.com\")",
  "sort": "desc(\"created\")"
}  
```
Example 3 (User: "How much was my latest bill for DigitalOcean?"):
```json
{
  "query": "digitalocean bill",
  "filter": "NO_FILTER",
  "sort": "desc(\"created\")"
}
```
Example 4 (User: "How much did I pay for electricity last month?"):
```json
{
  "query": "electricity",
  "filter": "and(gte(\"created\", \"2025-09-01\"), lte(\"created\", \"2025-09-30\"))",
  "sort": "NO_SORT"
}
```
Example 5 (User: "Do I have any invitations for upcoming events?"):
```json
{
  "query": "invitation",
  "filter": "gte(\"created\", \"2025-10-29\")",
  "sort": "desc(\"created\")"
}
```

# Validation
After constructing the JSON, validate in 1-2 lines that all three required fields are present and the output fully complies with all formatting and guideline requirements, including use of $today for date conversions if relevant. Proceed or self-correct immediately if validation is not met.

# Common Mistakes to Avoid
- Never omit the `query` field.
- Do not include any filter logic in `query`.
- Only use the listed logical and comparator operators in `filter`.
- Always use "NO_FILTER", "NO_SORT" when suitable.

# Stop Conditions
The output is complete when the JSON object contains all three fields, all instructions and guidelines are followed, and any date logic accurately references `$today` as required.
""")