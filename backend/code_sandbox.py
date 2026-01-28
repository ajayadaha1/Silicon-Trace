"""
Safe code execution sandbox for AI-generated Python code
Executes Plotly visualization code with security restrictions
"""
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
from typing import Any, Dict, Optional
import sys
from io import StringIO
import traceback
import signal
from contextlib import contextmanager


class TimeoutException(Exception):
    """Raised when code execution times out"""
    pass


@contextmanager
def timeout(seconds: int):
    """Context manager for execution timeout (Windows compatible)"""
    import threading
    
    def timeout_handler():
        raise TimeoutException(f"Code execution exceeded {seconds} seconds")
    
    timer = threading.Timer(seconds, timeout_handler)
    timer.start()
    try:
        yield
    finally:
        timer.cancel()


class CodeSandbox:
    """Safe execution environment for AI-generated code"""
    
    # Allowed imports
    SAFE_MODULES = {
        'pandas': pd,
        'pd': pd,
        'plotly.graph_objects': go,
        'go': go,
        'plotly.express': px,
        'px': px,
        'numpy': np,
        'np': np,
    }
    
    # Dangerous built-ins to remove
    DANGEROUS_BUILTINS = [
        'eval', 'exec', 'compile', '__import__',
        'open', 'input', 'file',
        'reload', 'execfile'
    ]
    
    def __init__(self, timeout_seconds: int = 30):
        self.timeout_seconds = timeout_seconds
    
    def execute(
        self,
        code: str,
        df: pd.DataFrame,
        additional_vars: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Safely execute Python code in restricted environment
        
        Args:
            code: Python code to execute (must create 'fig' variable)
            df: DataFrame to provide as 'df' variable
            additional_vars: Additional variables to make available
            
        Returns:
            Dict with 'success', 'figure', 'error', 'output', 'code'
        """
        # Prepare safe globals
        safe_globals = {
            '__builtins__': self._get_safe_builtins(),
            'pd': pd,
            'px': px,
            'go': go,
            'np': np,
            'df': df.copy(),  # Provide copy to prevent modification
        }
        
        if additional_vars:
            safe_globals.update(additional_vars)
        
        # Capture stdout/stderr
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout_capture = StringIO()
        stderr_capture = StringIO()
        
        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture
            
            # Execute with timeout
            with timeout(self.timeout_seconds):
                exec(code, safe_globals)
            
            # Get the figure
            if 'fig' not in safe_globals:
                return {
                    'success': False,
                    'error': 'Code must create a variable named "fig" containing the Plotly figure',
                    'code': code,
                    'output': stdout_capture.getvalue()
                }
            
            fig = safe_globals['fig']
            
            # Validate it's a Plotly figure
            if not isinstance(fig, (go.Figure, type(px.bar([1,2,3])))):
                return {
                    'success': False,
                    'error': f'Variable "fig" must be a Plotly figure, got {type(fig).__name__}',
                    'code': code,
                    'output': stdout_capture.getvalue()
                }
            
            return {
                'success': True,
                'figure': fig,
                'code': code,
                'output': stdout_capture.getvalue(),
                'stderr': stderr_capture.getvalue()
            }
            
        except TimeoutException as e:
            return {
                'success': False,
                'error': str(e),
                'code': code,
                'output': stdout_capture.getvalue()
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': f'{type(e).__name__}: {str(e)}',
                'traceback': traceback.format_exc(),
                'code': code,
                'output': stdout_capture.getvalue()
            }
        
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
    
    def _get_safe_builtins(self) -> Dict[str, Any]:
        """Get filtered built-in functions (remove dangerous ones)"""
        safe_builtins = {}
        original_builtins = __builtins__ if isinstance(__builtins__, dict) else __builtins__.__dict__
        
        for name, obj in original_builtins.items():
            if name not in self.DANGEROUS_BUILTINS:
                safe_builtins[name] = obj
        
        return safe_builtins
    
    def validate_code(self, code: str) -> Dict[str, Any]:
        """
        Validate code without executing it
        
        Returns:
            Dict with 'valid': bool, 'error': Optional[str]
        """
        # Check for dangerous patterns
        dangerous_patterns = [
            'import os',
            'import sys',
            'import subprocess',
            'import socket',
            '__import__',
            'eval(',
            'exec(',
            'compile(',
            'open(',
            'file(',
            'input(',
        ]
        
        for pattern in dangerous_patterns:
            if pattern in code:
                return {
                    'valid': False,
                    'error': f'Dangerous pattern detected: {pattern}'
                }
        
        # Try to compile
        try:
            compile(code, '<string>', 'exec')
            return {'valid': True, 'error': None}
        except SyntaxError as e:
            return {
                'valid': False,
                'error': f'Syntax error: {str(e)}'
            }
    
    def get_code_info(self, code: str) -> Dict[str, Any]:
        """
        Extract information about the code without executing
        
        Returns:
            Dict with 'imports', 'functions', 'variables'
        """
        info = {
            'imports': [],
            'functions': [],
            'variables': [],
            'has_fig': 'fig' in code
        }
        
        # Simple parsing (not AST-based for simplicity)
        lines = code.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('import ') or line.startswith('from '):
                info['imports'].append(line)
            elif line.startswith('def '):
                func_name = line.split('(')[0].replace('def ', '').strip()
                info['functions'].append(func_name)
            elif '=' in line and not line.startswith('#'):
                var_name = line.split('=')[0].strip()
                if var_name and var_name.isidentifier():
                    info['variables'].append(var_name)
        
        return info


# Singleton instance
_sandbox: Optional[CodeSandbox] = None


def get_sandbox(timeout_seconds: int = 30) -> CodeSandbox:
    """Get or create CodeSandbox instance"""
    global _sandbox
    if _sandbox is None:
        _sandbox = CodeSandbox(timeout_seconds)
    return _sandbox
