#!/usr/bin/env python3
"""
Code Analysis Agent - Analyzes ITILDesk code based on log findings
"""

from crewai import Agent, LLM
from sifra.tools.smart_file_reader_tool import smart_file_reader
from sifra.tools.confluence_tool import confluence_query_tool
from sifra.utils.config import Config
from sifra.utils.llm_config import LLMConfig


class CodeAnalysisAgent:
    """
    Code Analysis Agent - Investigates code files mentioned in log errors
    """
    
    def __init__(self, config: Config):
        """
        Initialize Code Analysis agent
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.tools = [smart_file_reader, confluence_query_tool]
        
        # Setup LLM configuration
        self.llm_config = LLMConfig(config)
        # Create proper CrewAI agent
        self._setup_agent()
    
    def _setup_agent(self):
        """Setup the CrewAI agent"""
        # Create custom LLM with higher token limit for code analysis
        cloudverse_llm = LLM(
            model="openai/anthropic-claude-3-5-sonnet-v2",
            api_key=self.config.llm.get('api_key', ''),
            base_url=self.config.llm.get('base_url', ''),
            max_tokens=8000  # Higher limit for code analysis
        )
        
        self.agent = Agent(
            role="Code Investigator",
            goal="Read code files using structured context to find root cause",
            backstory="""You investigate Rails code issues using structured input from log analysis.
            
            AVAILABLE TOOLS:
            - smart_file_reader: Read code files from the codebase
            - confluence_search: Search internal documentation and guides
            
            INPUT FORMAT:
            You receive JSON with:
            - error_analysis.specific_context: The unique aspect of this error
            - code_investigation.primary_file: Exact file to read
            - code_investigation.method_to_check: Specific method
            - code_investigation.investigation_focus: Questions to answer
            - code_investigation.log_evidence: Proof from logs
            
            WORKFLOW:
            1. Parse the JSON context from previous task
            2. (Optional) Search docs: confluence_search("feature name") if you need context
            3. Read: smart_file_reader(file_path=primary_file, method_name=method_to_check)
            4. Answer EACH investigation_focus question by examining the code
            5. Identify issues related to specific_context
            6. Validate: "Does this fix address [specific_context]?"
            
            When to use confluence_search:
            - Understanding a feature's expected behavior
            - Looking up deployment processes
            - Finding troubleshooting guides
            - Understanding authentication/SSO flows
            - Checking configuration requirements
            
            RULES:
            - Use the investigation_focus questions as your checklist
            - Connect your findings back to specific_context
            - Cite line numbers from the code you read
            - Validate your fix addresses the specific_context
            
            OUTPUT FORMAT:
            ```
            🎯 INVESTIGATION TARGET:
            [specific_context from input]
            
            📄 CODE READ:
            File: [primary_file]
            Method: [method_to_check]
            
            🔍 INVESTIGATION ANSWERS:
            Q1: [investigation_focus question 1]
            A1: [What you found in the code]
            
            Q2: [investigation_focus question 2]
            A2: [What you found in the code]
            
            ⚠️ ROOT CAUSE:
            [How the code behavior explains the specific_context issue]
            
            ✅ FIX (Line X):
            [Specific code change that addresses specific_context]
            
            ✓ VALIDATION:
            Does this fix address "[specific_context]"? [Yes/No and why]
            ```
            """,
            tools=self.tools,
            verbose=True,
            allow_delegation=False,
            llm=cloudverse_llm
        )

