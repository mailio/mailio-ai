selfquery_prompt = """
Your goal is to transform a user’s natural-language request into a JSON object matching this schema:
```{{ "query": string \\ text string to compare to document contents, "filter": string \\ logical condition statement for filtering documents, "sort": string \\ sorting statement for sorting documents }} ``` 

The query string should contain only text that is expected to match the contents of documents. Any conditions in the filter should not be mentioned in the query as well. 

A logical condition statement is composed of one or more comparison and logical operation statements. A comparison statement takes the form: 
`comp(attr, val)`: - `comp` (eq | ne | lt | lte | gt | gte | in | nin): comparator - `attr` (string): name of attribute to apply the comparison to - `val` (string): is the comparison value A logical operation statement takes the form `op(statement1, statement2, ...)`: - `op` (and | or): logical operator - `statement1`, `statement2`, ... (comparison statements or logical operation statements): one or more statements to apply the operation to 
Make sure that you only use the comparators and logical operators listed above and no others. 
Make sure that filters only refer to attributes that exist in the data source. 
Make sure that filters only use the attributed names with its function names if there are functions applied on them. 
Make sure that filters only use format `YYYY-MM-DD` when handling date data typed values. 
Make sure that filters take into account the descriptions of attributes and only make comparisons that are feasible given the type of data being stored. 
Make sure that filters are only used as needed. If there are no filters that should be applied return "NO_FILTER" for the filter value. 
Make sure you understand today, tomorrow, last month and convert them in current dates, not fictional dates. 

A sorting statement is composed one exactly one sorting statement. A sorting statement takes form `sort(attr, val)`: `sort` (desc | asc): comparator - `attr` (string): where attr is always only "created" field. 
Make sure that sorting is only used when needed. 
Make sure that sorting is only on "created" field.
Make sure that sorting is only used when needed. If there is no sorting that should be applied return "NO_SORT" for the sort value.
Make sure sorting only uses dates and the dates are in format `YYYY-MM-DD`. 
Make sure you understand today, tomorrow, last month and convert them in current dates, not fictional dates. 

Today's date: 
You’ll be given {{today}} in YYYY-MM-DD format.
- Convert “today”, “tomorrow”, “last month”, etc. into absolute dates.
 - If the query implies future semantics (contains words like next, upcoming, future, after), add a filter gte("created", "<{today}>" or tomorrow’s date).

<< Example 1. >> 
Data Source: ```json {{ "content": "meeting", "attributes": {{ "created": {{ "type": "date", "description": "email created on a date" }}, "from_email": {{ "type": "string", "description": "sent from email" }} }} }} ``` 

User Queries: ["When is my next meeting?", "Upcoming meetings", "next scheduled meeting", "anything coming up", "next appointment"]
Structured Request: ```{{ "query": "meeting", "filter": "and(qt(\"created\", \"2025-04-11\"))" }} ``` 

<< Example 2. >> 
Data Source: ```json {{ "content": "meeting", "attributes": {{ "created": {{ "type": "date", "description": "email created on a date" }}, "from_email": {{ "type": "string", "description": "sent from email" }} }} }} ``` 

User Query: The latest email from test@example.com: 
Structured Request: ```{{ "query": "meeting", "filter": "and(eq(\"from_email\", \"test@example.com\"))" }} ``` 

<< Example 3. >> 
Data Source: ```json {{ "content": "digitalocean bill", "attributes": {{ "created": {{ "type": "date", "description": "email created on a date" }}, "from_email": {{ "type": "string", "description": "sent from email" }} }} }} ``` 

User Query: how much was my latest bill for digitalocean 
Structured Request:
```json {{ "query": "digitalocean bill", "filter": "gte(\"created\": \"2025-01-01\")", "sort": "desc(\"created\")" }} ```

<< Example 4. >>
Data Source: ```json {{ "content": "digitalocean bill", "attributes": {{ "created": {{ "type": "date", "description": "email created on a date" }}, "from_email": {{ "type": "string", "description": "sent from email" }} }} }} ``` 

User query: when was my last healthcare visit?
Structured Request:
```json {{ "query": "healthcare", "sort": "desc(\"created\")" }} ```

<< Example 5. >>
Data Source: ```json {{ "content": "digitalocean bill", "attributes": {{ "created": {{ "type": "date", "description": "email created on a date" }}, "from_email": {{ "type": "string", "description": "sent from email" }} }} }} ``` 

User query: how much did I pay for electricity last month?
Structured Request: 
```json {{ "query": "electricity", "filter": "and(gte(\"created\": \"2025-03-01\"), lte(\"created\": \"2025-04-01\")" }} ```

<< Example 6. >>
Data Source: ```json {{ "content": "support ticket", "attributes": {{ "created": {{ "type": "date", "description": "email created on a date" }}, "from_email": {{ "type": "string", "description": "sender email address" }} }} }} ```
 
User query: What is the status of my latest support ticket?
Structured Request:
```json {{ "query": "support ticket", "filter": "gte(\"created\": \"2025-02-01\")", "sort": "desc(\"created\")" }} ```

<< Example 7. >>
Data Source: ```json {{ "content": "invitation", "attributes": {{ "created": {{ "type": "date", "description": "email created on a date" }}, "from_email": {{ "type": "string", "description": "sender email address" }} }} }} ```

Query: Do I have any invitations for upcoming events?
Structured response: 
```json {{ "query": "invitation", "filter": "NO_FILTER", "sort": "desc(\"created\")" }} ```

<< Example 8. >>
Data Source: ```json {{ "content": "invitation", "attributes": {{ "created": {{ "type": "date", "description": "email created on a date" }}, "from_email": {{ "type": "string", "description": "sender email address" }} }} }} ```

Query: where is my package from amazon
Structured response:
```json {{ "query": "amazon package", "filter": "gte(\"created\": \"2025-02-01\")", "sort": "desc(\"created\")" }} ```
"""

insights_prompt = """
Check the list of emails and extract insights from them.
Make sensible decision whether to include numbers section as described below based on the query and the content of the emails:  
Query: {query}
In case a query is a question, return the answer in the answer field describing the top email.
Return the insights in JSON format. Example:
{{
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