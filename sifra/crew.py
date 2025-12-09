#!/usr/bin/env python3
"""
Sifra Advanced Crew - Main orchestration class
"""

from crewai import Agent, Task, Crew
from sifra.agents.query_picker import QueryPicker
from sifra.agents.query_router_agent import QueryRouterAgent
from sifra.agents.support_ticket_reader import SupportTicketReader
from sifra.agents.account_agent import AccountAgent
from sifra.agents.log_url_generator import LogUrlGenerator
from sifra.agents.code_analysis_agent import CodeAnalysisAgent
from sifra.agents.code_assistant_agent import CodeAssistantAgent
from sifra.agents.slack_responder import SlackResponderAgent
from sifra.utils.config import Config
from sifra.tools.slack_tool import is_sifra_mention


class SifraAdvCrew:
    """
    Main crew class that orchestrates all Sifra Advanced agents
    """
    
    def __init__(self):
        """Initialize the crew with pure CrewAI structure"""
        self.config = Config()
        self._setup_agents()
        self._setup_tasks()
        self._setup_crew()
    
    def _setup_agents(self):
        """Setup all agents"""
        # Existing ticket analysis agents
        self.query_picker = QueryPicker(self.config)
        self.query_router = QueryRouterAgent(self.config)
        self.support_ticket_reader = SupportTicketReader(self.config)
        self.account_agent = AccountAgent(self.config)
        self.log_url_generator = LogUrlGenerator(self.config)
        self.code_analyzer = CodeAnalysisAgent(self.config)
        self.slack_responder = SlackResponderAgent(self.config)
        
        # New code assistant agents
        self.code_assistant = CodeAssistantAgent(self.config)
    
    def _setup_tasks(self):
        """Setup all tasks"""
        # Task 1: Pick query from Slack - Pure CrewAI Task object
        self.pick_query_task = Task(
            description="""
            Listen to Slack channel and pick queries or ticket IDs to investigate.
            
            Steps:
            1. Read the last message from Slack channel using the slack_reader tool
            2. Analyze if it contains a support ticket URL or general query
            3. Extract relevant information
            4. If ticket URL found, pass it to the next agent for analysis
            
            Use the slack_reader tool to get the message, then analyze it for:
            - Support ticket URLs (like freshdesk.com/tickets/...)
            - General queries or questions
            
            Return a JSON response with:
            - type: "ticket" or "general"
            - content: extracted ticket URL or general query
            - response: helpful response for the user
            """,
            agent=self.query_picker.agent,
            expected_output="JSON response with query analysis and ticket URL if found"
        )
        
        # Task 2: L3 Support Ticket Analysis
        self.analyze_ticket_task = Task(
            description="""
            As an expert L3 Support Engineer, perform comprehensive ticket analysis by reading ALL information sources.
            
            YOU MUST READ AND ANALYZE:
            
            1. FRESHOPS URL EXTRACTION:
               - Look for Freshops URLs in format: @https://freshops-admin.freshservice.com/accounts/623700
               - Extract the complete URL including account number
               - This URL will be sent to the account analysis agent
            
            2. ISSUE DESCRIPTION ANALYSIS:
               - Read the main ticket description thoroughly
               - Extract technical details, error messages, and symptoms
               - Identify the core problem the customer is facing
               - Note any system components or services mentioned
            
            3. SCREENSHOT ANALYSIS:
               - Use VisionTool to analyze ALL screenshots in the ticket
               - Look for error messages, console logs, network errors
               - Identify UI issues, broken functionality, or system failures
               - Extract any technical details visible in screenshots
               - Note browser console errors, API response codes, or system messages
            
            4. STEPS TO REPRODUCE ANALYSIS:
               - Extract and analyze the exact reproduction steps provided
               - Identify environmental factors (browser, OS, network)
               - Note specific user actions that trigger the issue
               - Understand the expected vs actual behavior
            
            5. CONVERSATION HISTORY ANALYSIS:
               - Read ALL conversations between agents and customers
               - Track the troubleshooting progression and attempted solutions
               - Identify what has been tried and what failed
               - Extract additional technical details from agent responses
               - Note any escalation reasons or unresolved questions
            
            6. COMPREHENSIVE TICKET INFORMATION:
               - Read ticket priority, status, and category
               - Extract customer information and contact details
               - Note timestamps and timeline of the issue
               - Identify any related tickets or previous incidents
               - Extract any log snippets, error codes, or technical data
            
            CRITICAL REQUIREMENTS:
            - Use freshdesk_reader tool to get complete ticket data
            - Analyze screenshots with VisionTool for visual errors
            - Extract Freshops URLs for account analysis
            - Read conversation history between all agents
            - Check for downloaded_attachments field - HAR files are automatically downloaded
            - If HAR files are present, note them for the Log Analysis agent
            - Provide structured L3 analysis with actionable insights
            
            NOTE: HAR files (.har) are automatically downloaded and saved to project root.
            The downloaded_attachments field contains: {filename: local_path}
            Mention HAR file availability in your analysis for auth issues.
            
            OUTPUT FORMAT:
            FRESHOPS_URL: @https://freshops-admin.freshservice.com/accounts/XXXXXX (if found)
            HAR_FILES: [list of downloaded HAR filenames] (if any)
            
            COMPLETE_TICKET_ANALYSIS:
            - ISSUE SUMMARY: Technical description from all sources
            - ERROR DETAILS: Errors from description, screenshots, conversations
            - REPRODUCTION STEPS: Complete steps with environmental factors
            - CONVERSATION INSIGHTS: Key findings from agent discussions
            - SCREENSHOT ANALYSIS: Technical details from visual analysis
            - TECHNICAL FINDINGS: Root cause analysis from all sources
            - RECOMMENDED ACTIONS: Next steps based on complete analysis
            - LOG SEARCH TERMS: Keywords for Haystack searches
            
            Be thorough - read EVERYTHING in the ticket, not just the description.
            """,
            agent=self.support_ticket_reader.agent,
            expected_output="Structured L3 analysis with Freshops URL separated for account agent and complete ticket details for log URL generator",
            context=[self.pick_query_task]
        )
        
        # Task 3: Extract Account Details from Freshops URL
        self.analyze_account_task = Task(
            description="""
            Extract specific account information from the Freshops URL provided by the L3 Support Engineer.
            
            Steps:
            1. Look for the FRESHOPS_URL line in the ticket analysis
            2. Extract the URL (format: @https://freshops-admin.freshservice.com/accounts/XXXXXX)
            3. Use the account_reader tool to fetch account details from this URL
            4. Return structured account information
            
            The account_reader tool will extract:
            - Account ID, Name, Subscription ID
            - Shard, Pod, Contact information
            - Billing details (plan, revenue, renewal)
            - API limits and usage
            - Security settings
            - Organization details
            
            If no FRESHOPS_URL is found, return: "No Freshops URL found in ticket analysis"
            
            Focus on extracting the key account summary information.
            """,
            agent=self.account_agent.agent,
            expected_output="Structured JSON with account details including billing, limits, and configuration information",
            context=[self.analyze_ticket_task]
        )
        
        # Task 4: Search and Analyze Haystack Logs (with Triage + HAR Priority)
        self.generate_log_urls_task = Task(
            description="""
            Search Haystack logs with smart triage. HAR UUIDs are THE most precise search terms.
            
            Search Strategy (Priority Order):
            
            PRIORITY 1 - HAR UUIDs (Most Precise):
            1. Check ticket analysis for HAR_FILES or downloaded_attachments field
            2. If HAR files present: Use har_parser(file_path="filename.har") with the filename
               (Files are already downloaded to project root by freshdesk_reader)
            3. Extract UUIDs AND TIMESTAMPS from failed requests
            4. Use ONLY UUIDs in query_string (e.g., "uuid-1 OR uuid-2 OR uuid-3")
            5. Use HAR timestamps (earliest/latest ±30 min buffer) for time range
            6. Don't add other search terms - UUIDs are unique and sufficient
            
            PRIORITY 2 - Haystack URL:
            5. If no HAR: Check for Haystack URLs in ticket
            6. Extract parameters from URL and search
            
            PRIORITY 3 - Manual Search:
            7. If neither: Build query from account ID, error messages, etc.
            
            Apply TRIAGE RULES and output structured JSON.auto
            
            **KEY: HAR provides UUIDs (exact failed requests) + timestamps (exact time range)!**
            
            TRIAGE RULES (CRITICAL):
            
            Rule 1 - NO LOGS FOUND:
            If no Haystack URL in ticket AND search returns empty/insufficient results:
            → Set "first_response": "Please reproduce the issue and provide Haystack log URL or HAR file."
            → Add "triage_reason": "Insufficient log data"
            
            Rule 2 - AUTHENTICATION ISSUES:
            If ticket mentions: login, logout, authentication, authorization, SSO, SAML, OAuth, session, token, 401, 403:
            
            Priority order:
            → FIRST: Check for HAR file
              → If HAR found: Parse UUIDs and use ONLY UUIDs for search (most precise)
              → Proceed with analysis
            
            → SECOND: Check for Haystack URL
              → If Haystack URL found: Use it
              → Proceed with analysis
            
            → If NEITHER HAR nor Haystack URL:
              → Set "first_response": "Please provide HAR file. This appears to be an authentication issue handled by FID platform team. Once HAR file is provided, we can move this to FID team."
              → Add "issue_category": "Authentication/Authorization"
              → Add "escalation_team": "FID Platform Team"
            
            → Include "data_source_used": "har_uuids" or "haystack_url" or "manual" in JSON
            
            Rule 3 - LOGS FOUND:
            If logs are found and not auth issue:
            → Omit "first_response" field
            → Provide full structured analysis with code_investigation
            
            Output JSON with:
            - first_response (only if Rule 1 or Rule 2 applies)
            - error_analysis with specific_context
            - code_investigation with investigation_focus questions
            - Validation fields for triage decisions
            """,
            agent=self.log_url_generator.agent,
            expected_output="Analysis of logs including error details, controller/action, file to check, and key findings",
            context=[self.analyze_ticket_task, self.analyze_account_task]  # Only ticket and account context, not everything
        )
        
        # Task 5: Analyze Code Using Structured Context (Skip if First Response needed)
        self.analyze_code_task = Task(
            description="""
            Use STRUCTURED CONTEXT from log analysis to investigate code.
            
            IMPORTANT: Check if previous task has "first_response" field:
            - If "first_response" exists → Skip code analysis, pass through the first_response
            - If no "first_response" → Proceed with normal code analysis
            
            For code analysis (when no first_response):
            You will receive JSON with these fields:
            - error_analysis.specific_context (e.g., "Agent type: Occasional")
            - code_investigation.primary_file (exact file path)
            - code_investigation.method_to_check (method name)
            - code_investigation.investigation_focus (questions to answer)
            - code_investigation.log_evidence (proof from logs)
            
            Your job:
            1. Check for "first_response" - if present, output:
               "⚠️ TRIAGE DECISION: [first_response message]"
            2. If no first_response, extract structured data and analyze code
            3. Read the specified file/method using smart_file_reader
            4. Answer EACH investigation_focus question
            5. Connect findings to specific_context
            6. Suggest fix and validate it addresses specific_context
            
            This allows early exit when investigation not possible.
            """,
            agent=self.code_analyzer.agent,
            expected_output="Either triage message (if first_response) OR structured code analysis with validation",
            context=[self.generate_log_urls_task]
        )
        
        # Task 6: Send formatted response back to Slack
        self.send_slack_response_task = Task(
            description="""
            Format the complete analysis results and send them back to Slack as a thread reply.
            
            You have access to all previous task results:
            1. Ticket information (ID, subject, description, priority)
            2. Account details (name, shard, pod, plan, state)
            3. Log analysis (errors found, timestamps, haystack URLs)
            4. Code analysis (files, methods, root cause, recommendations)
            
            YOUR JOB:
            1. Review all the analysis results from previous tasks
            2. Format them into a clear, structured message with these sections:
               - 🎯 *SUMMARY* (2-3 line overview of the issue)
               - 🎫 *TICKET* (ID, subject, priority, status)
               - 🏢 *ACCOUNT* (name, shard, pod, plan, state)
               - 📝 *LOG ANALYSIS* (error type, controller, timestamps, haystack URL)
               - 💻 *ROOT CAUSE* (file, method, specific issue found)
               - ✅ *RECOMMENDATION* (suggested fix or next steps)
            3. Use the slack_replier tool to send the formatted message
            
            FORMATTING RULES:
            - Use emojis for visual sections
            - Use *bold* for important text using asterisks
            - Keep bullet points concise
            - Include clickable URLs where relevant
            - Keep total message under 3000 characters
            - Use "N/A" if any information is missing
            
            EXAMPLE FORMAT:
            🎯 *ANALYSIS COMPLETE*
            SSO authentication failing for enterprise customer due to token validation issue.
            
            🎫 *Ticket:* #12345 - SSO Auth Error
            • Priority: High | Status: Open
            • Link: [View Ticket](ticket_url)
            
            🏢 *Account:* Oak Valley Hospital
            • Shard: shard_10 | Pod: poduseast1  
            • Plan: Enterprise | State: active
            
            📝 *Log Analysis:*
            • Error: Oauth::Unauthorized in SessionsController#callback
            • Time: 2024-11-12 10:30:45 UTC
            • [View Logs](haystack_url)
            
            💻 *Root Cause:*
            • File: app/controllers/sessions_controller.rb
            • Method: validate_oauth_token
            • Issue: Token validation failing due to expired certificates
            
            ✅ *Recommendation:*
            Refresh OAuth certificates and restart authentication service. Check certificate expiry dates.
            
            After formatting, immediately use the slack_replier tool to send this message.
            """,
            agent=self.slack_responder.agent,
            expected_output="Confirmation that the formatted analysis has been sent to Slack successfully",
            context=[
                self.pick_query_task,
                self.analyze_ticket_task,
                self.analyze_account_task,
                self.generate_log_urls_task,
                self.analyze_code_task
            ]
        )
        
        # Task 7: Code Assistant - Answer code queries
        self.code_assistant_task = Task(
            description="""
            Answer the user's code query using codebase search and documentation.
            
            WORKFLOW:
            1. Understand what the user is asking (code flow, method location, implementation, etc.)
            2. Search codebase:
               - Use code_searcher(query="AgentsController") to find classes
               - Use smart_file_reader(file_path="...", method_name="update") to read methods
               - Search ONE term at a time (don't combine "agents_controller update")
            3. Query confluence_search for architecture docs if needed
            4. Format answer with:
               - Clear structure with emojis (📝🔍💡✅)
               - File paths and line numbers
               - Code snippets
            5. **CRITICAL**: Use slack_replier to send your formatted answer!
            
            Example for "explain agent update flow":
            → code_searcher(query="AgentsController")
            → smart_file_reader(file_path="app/controllers/agents_controller.rb", method_name="update")
            → Format and send via slack_replier
            
            Don't skip step 5!
            """,
            agent=self.code_assistant.agent,
            expected_output="Formatted code analysis response sent to Slack"
        )
    
    def _setup_crew(self):
        """Setup the crew with agents and tasks"""
        self.crew = Crew(
            agents=[
                self.query_picker.agent,
                self.support_ticket_reader.agent,
                self.account_agent.agent,
                self.log_url_generator.agent,
                self.code_analyzer.agent,
                self.slack_responder.agent
            ],
            tasks=[
                self.pick_query_task,
                self.analyze_ticket_task,
                self.analyze_account_task,
                self.generate_log_urls_task,
                self.analyze_code_task,
                self.send_slack_response_task
            ],
            verbose=True,
            memory=False
        )
    
    def run(self, inputs=None):
        """
        Run the crew using pure CrewAI orchestration with intelligent routing
        
        Supports two workflows:
        1. Ticket Analysis (existing): Slack → Ticket → Account → Logs → Code → Slack
        2. Code Assistant (NEW): Slack → Code Query → Slack
        
        Args:
            inputs (dict): Input data for the crew
            
        Returns:
            dict: Results from the crew execution
        """
        if inputs is None:
            inputs = {"message": "Default test message"}
        
        print("🤖 Starting Sifra Advanced...")
        print("   📨 Reading Slack message to determine workflow...")
        print("")
        
        # Create a simple crew just to read the Slack message and check for @sifra
        from sifra.agents.query_router_agent import QueryRouterAgent
        
        reader_crew = Crew(
            agents=[self.query_picker.agent],
            tasks=[self.pick_query_task],
            verbose=False,
            memory=False
        )
        
        # Read the message
        query_result = reader_crew.kickoff(inputs=inputs)
        query_text = str(query_result) if query_result else ""
        
        # Check if this is a @sifra mention (code query)
        if is_sifra_mention():
            print("   💻 @sifra detected! Checking query type...")
            
            # Route the query
            query_type = QueryRouterAgent.quick_route(query_text)
            
            if query_type == "CODE_QUERY":
                print("   🔍 Code query detected - activating Code Assistant workflow")
                print("   📋 Workflow: Code Search → Documentation → Slack Reply")
                print("")
                
                # Create a dynamic task with the actual query embedded
                code_query_task = Task(
                    description=f"""
                    USER'S QUESTION: "{query_text}"
                    
                    Answer this question using your tools and send the response via slack_replier.
                    Remember: Search ONE term at a time, read files, format well, and call slack_replier!
                    """,
                    agent=self.code_assistant.agent,
                    expected_output="Detailed code analysis sent to Slack via slack_replier"
                )
                
                # Create crew with code assistant workflow
                code_crew = Crew(
                    agents=[self.code_assistant.agent],
                    tasks=[code_query_task],
                    verbose=True,
                    memory=False
                )
                
                result = code_crew.kickoff(inputs={"query": query_text})
                
                print("")
                print("✅ Code Assistant workflow completed!")
                print("📬 Answer sent back to Slack!")
                
                return {
                    "status": "success",
                    "result": str(result),
                    "workflow": "code_assistant"
                }
            else:
                # It's a ticket URL, fall through to ticket analysis
                print("   🎫 Ticket URL detected - activating Ticket Analysis workflow")
        else:
            # No @sifra mention - check if it's a ticket URL
            import re
            ticket_url_patterns = [
                r'freshdesk\.com/a/tickets/\d+',
                r'freshservice\.com/a/tickets/\d+',
            ]
            
            has_ticket_url = any(re.search(pattern, query_text, re.IGNORECASE) for pattern in ticket_url_patterns)
            
            if not has_ticket_url:
                # No @sifra and no ticket URL - ignore this message
                print("   ⚠️  No @sifra mention and no ticket URL found - ignoring message")
                print("   💡 Tip: Tag @sifra for code queries or provide a ticket URL for analysis")
                print("")
                return {
                    "status": "ignored",
                    "result": "Message ignored - no @sifra mention or ticket URL",
                    "workflow": "none"
                }
            
            # Has ticket URL but no @sifra - use ticket analysis
            print("   🎫 Ticket URL detected - activating Ticket Analysis workflow")
        
        print("   📋 Workflow: Ticket → Account → Logs → Code → Slack Reply")
        print("")
        
        # Run ticket analysis workflow (existing) - skip query picker since we already ran it
        analysis_crew = Crew(
            agents=[
                self.support_ticket_reader.agent,
                self.account_agent.agent,
                self.log_url_generator.agent,
                self.code_analyzer.agent,
                self.slack_responder.agent
            ],
            tasks=[
                self.analyze_ticket_task,
                self.analyze_account_task,
                self.generate_log_urls_task,
                self.analyze_code_task,
                self.send_slack_response_task
            ],
            verbose=True,
            memory=False
        )
        
        result = analysis_crew.kickoff(inputs={"ticket_url": query_text if 'query_text' in locals() else str(query_result)})
        
        print("")
        print("✅ Ticket Analysis workflow completed!")
        print("📬 Analysis results sent back to Slack!")
        
        return {
            "status": "success",
            "result": str(result),
            "workflow": "ticket_analysis"
        }
