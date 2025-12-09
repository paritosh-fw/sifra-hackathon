#!/usr/bin/env python3
"""
Smart File Reader Tool - Reads specific sections of code files intelligently
"""

from crewai.tools import BaseTool
from typing import Optional, Type
from pydantic import BaseModel, Field
import os
import re


class SmartFileReaderInput(BaseModel):
    """Input schema for SmartFileReader"""
    file_path: str = Field(description="Relative path from itildesk_2 root (e.g., 'app/controllers/agents_controller.rb')")
    method_name: Optional[str] = Field(default=None, description="Optional: specific method/function to focus on (e.g., 'show', 'create')")
    context_lines: int = Field(default=5, description="Number of context lines before/after the method (reduced for efficiency)")


class SmartFileReaderTool(BaseTool):
    name: str = "smart_file_reader"
    description: str = """
    Smart file reader that reads code files from the ITILDesk codebase.
    
    Use this tool to read specific code files mentioned in log errors.
    You can optionally specify a method/function name to focus on that specific section.
    
    Input format:
    - file_path: Relative path from itildesk_2 root (e.g., "app/controllers/agents_controller.rb")
    - method_name: (Optional) Specific method to focus on (e.g., "show", "create", "update")
    - context_lines: (Optional) Number of lines of context around the method (default: 10)
    
    Examples:
    - file_path="app/controllers/agents_controller.rb", method_name="show"
    - file_path="app/models/agent.rb", method_name="change_type"
    - file_path="app/views/agents/show.html.erb"
    """
    args_schema: Type[BaseModel] = SmartFileReaderInput
    codebase_root: str = "/Users/paritoshagarwal/code/itildesk_2"
    
    def _run(self, file_path: str, method_name: Optional[str] = None, context_lines: int = 5) -> str:
        """
        Read a code file intelligently, focusing on specific methods if requested
        """
        try:
            # Build full path
            full_path = os.path.join(self.codebase_root, file_path)
            
            # Check if file exists
            if not os.path.exists(full_path):
                return f"❌ File not found: {file_path}\nSearched at: {full_path}"
            
            # Read the file
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
            
            # If no method specified, return first 30 lines with summary (reduced for context)
            if not method_name:
                total_lines = len(lines)
                preview_lines = min(30, total_lines)
                preview = '\n'.join(lines[:preview_lines])
                
                return f"""✅ File: {file_path}
📊 Total lines: {total_lines}
📄 Showing first {preview_lines} lines:

{preview}

{'...(file continues)' if total_lines > preview_lines else ''}

💡 TIP: Specify method_name parameter to focus on a specific method/function."""
            
            # Try to find the method
            method_start, method_end = self._find_method(lines, method_name, file_path)
            
            if method_start is None:
                # Method not found, return file summary
                return f"""⚠️ Method '{method_name}' not found in {file_path}

📊 File info:
- Total lines: {len(lines)}
- File type: {self._detect_file_type(file_path)}

Available methods/functions in this file:
{self._list_methods(lines, file_path)}

💡 Try one of the methods listed above."""
            
            # Extract method with context
            start_line = max(0, method_start - context_lines)
            end_line = min(len(lines), method_end + context_lines)
            
            method_content = '\n'.join(lines[start_line:end_line])
            
            return f"""✅ File: {file_path}
🎯 Method: {method_name}
📍 Lines: {method_start + 1} - {method_end + 1}
📊 Total file lines: {len(lines)}

{method_content}

---
💡 Showing lines {start_line + 1} to {end_line + 1} (includes {context_lines} lines of context)"""
            
        except Exception as e:
            return f"❌ Error reading file {file_path}: {str(e)}"
    
    def _find_method(self, lines: list, method_name: str, file_path: str) -> tuple:
        """Find the start and end line of a method/function"""
        file_ext = os.path.splitext(file_path)[1]
        
        # Ruby methods
        if file_ext == '.rb':
            return self._find_ruby_method(lines, method_name)
        # JavaScript/TypeScript
        elif file_ext in ['.js', '.ts', '.jsx', '.tsx']:
            return self._find_js_method(lines, method_name)
        # Python
        elif file_ext == '.py':
            return self._find_python_method(lines, method_name)
        else:
            # Generic search for any language
            return self._find_generic_method(lines, method_name)
    
    def _find_ruby_method(self, lines: list, method_name: str) -> tuple:
        """Find Ruby method definition"""
        method_start = None
        indent_level = None
        
        for i, line in enumerate(lines):
            # Look for "def method_name"
            if re.match(rf'^\s*def\s+{re.escape(method_name)}\b', line):
                method_start = i
                indent_level = len(line) - len(line.lstrip())
                break
        
        if method_start is None:
            return None, None
        
        # Find the end of the method
        method_end = len(lines) - 1
        for i in range(method_start + 1, len(lines)):
            line = lines[i]
            current_indent = len(line) - len(line.lstrip())
            
            # Check for 'end' at same or lower indent level
            if current_indent <= indent_level and re.match(r'^\s*end\b', line):
                method_end = i
                break
        
        return method_start, method_end + 1
    
    def _find_js_method(self, lines: list, method_name: str) -> tuple:
        """Find JavaScript/TypeScript method/function"""
        method_start = None
        
        patterns = [
            rf'^\s*function\s+{re.escape(method_name)}\s*\(',
            rf'^\s*{re.escape(method_name)}\s*[:=]\s*function\s*\(',
            rf'^\s*{re.escape(method_name)}\s*\([^)]*\)\s*{{',
            rf'^\s*async\s+{re.escape(method_name)}\s*\(',
        ]
        
        for i, line in enumerate(lines):
            for pattern in patterns:
                if re.search(pattern, line):
                    method_start = i
                    break
            if method_start is not None:
                break
        
        if method_start is None:
            return None, None
        
        # Find matching closing brace
        brace_count = 0
        method_end = len(lines) - 1
        
        for i in range(method_start, len(lines)):
            brace_count += lines[i].count('{')
            brace_count -= lines[i].count('}')
            if brace_count == 0 and '{' in lines[method_start]:
                method_end = i
                break
        
        return method_start, method_end + 1
    
    def _find_python_method(self, lines: list, method_name: str) -> tuple:
        """Find Python method/function"""
        method_start = None
        indent_level = None
        
        for i, line in enumerate(lines):
            if re.match(rf'^\s*def\s+{re.escape(method_name)}\s*\(', line):
                method_start = i
                indent_level = len(line) - len(line.lstrip())
                break
        
        if method_start is None:
            return None, None
        
        # Find end of method (next def/class at same or lower indent)
        method_end = len(lines) - 1
        for i in range(method_start + 1, len(lines)):
            line = lines[i]
            if line.strip():  # Non-empty line
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= indent_level and re.match(r'^\s*(def|class)\s+', line):
                    method_end = i - 1
                    break
        
        return method_start, method_end + 1
    
    def _find_generic_method(self, lines: list, method_name: str) -> tuple:
        """Generic method finder for any language"""
        method_start = None
        
        for i, line in enumerate(lines):
            if method_name in line and ('def' in line or 'function' in line):
                method_start = i
                break
        
        if method_start is None:
            return None, None
        
        # Return 30 lines as a reasonable chunk
        method_end = min(len(lines), method_start + 30)
        return method_start, method_end
    
    def _list_methods(self, lines: list, file_path: str) -> str:
        """List all methods/functions found in the file"""
        file_ext = os.path.splitext(file_path)[1]
        methods = []
        
        if file_ext == '.rb':
            pattern = r'^\s*def\s+(\w+)'
        elif file_ext in ['.js', '.ts', '.jsx', '.tsx']:
            pattern = r'^\s*(?:function\s+)?(\w+)\s*[:=]?\s*(?:function\s*)?\('
        elif file_ext == '.py':
            pattern = r'^\s*def\s+(\w+)\s*\('
        else:
            pattern = r'^\s*(?:def|function)\s+(\w+)'
        
        for line in lines:
            match = re.search(pattern, line)
            if match:
                methods.append(match.group(1))
        
        if not methods:
            return "No methods found"
        
        return '\n'.join([f"  - {m}" for m in methods[:20]])  # Show first 20
    
    def _detect_file_type(self, file_path: str) -> str:
        """Detect the programming language/file type"""
        ext_map = {
            '.rb': 'Ruby',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.py': 'Python',
            '.erb': 'ERB Template',
            '.html': 'HTML',
            '.css': 'CSS',
            '.scss': 'SCSS',
            '.java': 'Java',
            '.go': 'Go',
        }
        
        ext = os.path.splitext(file_path)[1]
        return ext_map.get(ext, f'Unknown ({ext})')


# Create the tool instance
smart_file_reader = SmartFileReaderTool()

