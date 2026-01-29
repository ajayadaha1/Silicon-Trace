"""
Nabu AI Platform Client for Silicon Trace
Provides intelligent data analysis, code generation, and conversational analytics
"""
import httpx
import json
from typing import List, Dict, Optional, Any
import pandas as pd
from datetime import datetime


class NabuClient:
    """Client for AMD Nabu AI Platform"""
    
    def __init__(self, api_token: str, base_url: str = "https://intelligence.amd.com/nabu/prod"):
        self.api_token = api_token
        self.base_url = base_url
        self.chat_endpoint = f"{base_url}/nabu_chat"
        self.headers = {
            "Content-Type": "application/json",
            "Ocp-Apim-Subscription-Key": api_token,
            "x-nabu-key": api_token
        }
    
    async def chat(
        self,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        model_name: str = "gpt-4o",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        amd_search: bool = False,
        chat_id: Optional[str] = None,
        mcp_servers: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Send a chat message to Nabu AI
        
        Args:
            user_prompt: The user's message
            history: Conversation history in format [{"role": "user", "content": "..."}, ...]
            model_name: Model to use (default: gpt-4o)
            temperature: Randomness (0-1)
            max_tokens: Max response length
            amd_search: Enable AMD internal knowledge search
            chat_id: Optional chat session ID
            
        Returns:
            Response from Nabu with assistant's message
        """
        payload = {
            "chat_id": chat_id or "",
            "user_prompt": user_prompt,
            "model_prompt": "",
            "history": history or [],
            "model_name": model_name,
            "amd_search_toggle": amd_search,
            "web_search_toggle": False,
            "file_upload_toggle": False,
            "generate_title_toggle": False,
            "restricted": False,
            "agents": [],
            "image_paths": [],
            "tokens": {},
            "temperature": temperature,
            "k": 3,
            "reasoning_effort": "",
            "max_tokens": max_tokens,
            "org_group_search_toggle": False,
            "McpTools": mcp_servers or []
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    self.chat_endpoint,
                    headers=self.headers,
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                print(f"Nabu API Response: {result}")
                return result
            except httpx.HTTPStatusError as e:
                print(f"Nabu API Error: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                print(f"Nabu API Exception: {str(e)}")
                raise
    
    async def analyze_dataframe(
        self,
        df: pd.DataFrame,
        focus_areas: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Automatically analyze a dataframe and extract insights
        
        Args:
            df: DataFrame to analyze
            focus_areas: Optional list of areas to focus on (e.g., ['failures', 'customers', 'trends'])
            
        Returns:
            Structured insights with metrics, patterns, anomalies, recommendations
        """
        # Prepare data summary
        summary = {
            "shape": df.shape,
            "columns": df.columns.tolist(),
            "dtypes": df.dtypes.astype(str).to_dict(),
            "sample": df.head(5).astype(str).to_dict(orient='records'),
            "missing": df.isnull().sum().to_dict(),
            "nunique": df.nunique().to_dict()
        }
        
        # Build analysis prompt
        prompt = f"""Analyze this hardware failure dataset and provide comprehensive insights:

DATASET SUMMARY:
- Shape: {summary['shape'][0]} rows × {summary['shape'][1]} columns
- Columns: {', '.join(summary['columns'])}
- Sample data: {json.dumps(summary['sample'][:3], indent=2)}

TASK:
Provide a structured analysis in JSON format with:
1. "key_metrics": {{
     "total_assets": <number>,
     "failure_rate_pct": <percentage>,
     "top_customer": "<name>",
     "most_common_error": "<error>",
     "avg_failures_per_customer": <number>
   }}

2. "insights": [
     {{"title": "<short title>", "description": "<detailed finding>", "impact": "<high|medium|low>"}},
     ...top 5 insights
   ]

3. "anomalies": [
     {{"type": "<anomaly type>", "description": "<what's unusual>", "severity": "<high|medium|low>"}},
     ...
   ]

4. "recommendations": [
     "<actionable recommendation 1>",
     "<actionable recommendation 2>",
     ...
   ]

5. "trend_analysis": {{
     "patterns": ["<pattern 1>", "<pattern 2>"],
     "predictions": ["<prediction 1>", "<prediction 2>"]
   }}

Focus on: {', '.join(focus_areas) if focus_areas else 'all aspects'}

Return ONLY valid JSON, no markdown formatting."""

        response = await self.chat(
            user_prompt=prompt,
            temperature=0.3,  # Lower for more factual analysis
            max_tokens=3000
        )
        
        # Parse response
        try:
            # Extract JSON from response
            content = response.get('responseText', response.get('response', response.get('message', '')))
            # Try to parse as JSON
            if isinstance(content, str):
                # Remove markdown code blocks if present
                content = content.strip()
                if content.startswith('```'):
                    content = content.split('```')[1]
                    if content.startswith('json'):
                        content = content[4:]
                    content = content.strip()
                    # Remove the closing ```
                    if content.endswith('```'):
                        content = content[:-3].strip()
                analysis = json.loads(content)
            else:
                analysis = content
                
            return {
                "success": True,
                "analysis": analysis,
                "raw_response": response
            }
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Failed to parse AI response as JSON: {str(e)}",
                "raw_response": response
            }
    
    async def generate_visualization_code(
        self,
        request: str,
        df: pd.DataFrame,
        data_summary: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Generate Plotly visualization code based on natural language request
        
        Args:
            request: Natural language description of desired visualization
            df: DataFrame containing the data
            data_summary: Optional pre-computed summary of the data
            
        Returns:
            Generated Python code as string
        """
        if data_summary is None:
            data_summary = {
                "columns": df.columns.tolist(),
                "shape": df.shape,
                "sample": df.head(3).astype(str).to_dict(orient='records'),
                "dtypes": df.dtypes.astype(str).to_dict()
            }
        
        prompt = f"""Generate Plotly Python code for the following visualization request:

REQUEST: {request}

AVAILABLE DATA:
- Columns: {', '.join(data_summary['columns'])}
- Data types: {json.dumps(data_summary['dtypes'], indent=2)}
- Sample data (first 3 rows): {json.dumps(data_summary['sample'], indent=2)}
- Shape: {data_summary['shape'][0]} rows × {data_summary['shape'][1]} columns

REQUIREMENTS:
1. Use plotly.express or plotly.graph_objects
2. Data is available as 'df' (pandas DataFrame)
3. Create a variable named 'fig' for the final figure
4. Include proper titles, labels, and styling
5. Handle missing data appropriately
6. Return ONLY executable Python code, no explanations
7. Do NOT include ```python markers or any markdown
8. For timeline/time-series with trendlines: aggregate counts over time first, then apply trendline
9. NEVER use trendline='ols' with categorical y-axis data
10. BAR CHARTS REQUIRE NUMERIC Y-VALUES - always aggregate categorical data first

IMPORTS AVAILABLE:
- import plotly.express as px
- import plotly.graph_objects as go
- import pandas as pd
- import numpy as np

Example output format:
import plotly.express as px
fig = px.bar(df, x='column1', y='column2', title='My Chart')
fig.update_layout(template='plotly_white')

IMPORTANT FOR BAR CHARTS:
- Bar charts MUST have numeric y-values (counts, sums, averages, etc.)
- If user wants "bar graph of failures", count/aggregate the data first
- Example: filtered_df.groupby('category').size().reset_index(name='count')
- Then plot: px.bar(aggregated_df, x='category', y='count')
- NEVER put categorical columns directly on y-axis

IMPORTANT FOR TIMELINE CHARTS:
- If user wants "timeline with trend line", create a count/aggregation over time
- Example: df.groupby(df['timestamp_col'].dt.date).size().reset_index(name='count')
- Then use trendline='ols' on the numeric count column

Generate the code now:"""

        response = await self.chat(
            user_prompt=prompt,
            temperature=0.2,  # Low temperature for precise code generation
            max_tokens=2000
        )
        
        # Extract code from response
        content = response.get('responseText', response.get('response', response.get('message', '')))
        
        # Clean up the code
        code = self._extract_code(content)
        
        return {
            "success": True,
            "code": code,
            "raw_response": response
        }
    
    async def investigate(
        self,
        topic: str,
        df: pd.DataFrame,
        max_steps: int = 5
    ) -> Dict[str, Any]:
        """
        Perform multi-step root cause analysis investigation
        
        Args:
            topic: Investigation topic/question
            df: Dataset to investigate
            max_steps: Maximum investigation steps
            
        Returns:
            Investigation results with steps, findings, and recommendations
        """
        data_summary = {
            "columns": df.columns.tolist(),
            "shape": df.shape,
            "sample": df.head(5).astype(str).to_dict(orient='records')
        }
        
        prompt = f"""You are a hardware failure analysis expert. Investigate this issue:

INVESTIGATION TOPIC: {topic}

AVAILABLE DATA:
- Columns: {', '.join(data_summary['columns'])}
- Total records: {data_summary['shape'][0]}
- Sample: {json.dumps(data_summary['sample'][:2], indent=2)}

Perform a systematic investigation with these steps:
1. Define hypothesis
2. Identify relevant data points
3. Analyze patterns
4. Draw conclusions
5. Provide recommendations

Return a JSON structure:
{{
  "hypothesis": "<your initial hypothesis>",
  "steps": [
    {{
      "number": 1,
      "title": "<step title>",
      "description": "<what you're investigating>",
      "findings": "<what you discovered>",
      "data_needed": ["<column1>", "<column2>"]
    }},
    ...
  ],
  "conclusion": "<final conclusion>",
  "root_causes": ["<cause 1>", "<cause 2>"],
  "recommendations": ["<action 1>", "<action 2>"],
  "confidence": "<high|medium|low>"
}}

Return ONLY valid JSON."""

        response = await self.chat(
            user_prompt=prompt,
            temperature=0.4,
            max_tokens=3000
        )
        
        # Parse response
        try:
            content = response.get('responseText', response.get('response', response.get('message', '')))
            if isinstance(content, str):
                content = content.strip()
                # Remove Nabu signature
                if 'This response was generated by Nabu.' in content:
                    content = content.replace('This response was generated by Nabu.', '').strip()
                # Remove markdown code blocks
                if content.startswith('```'):
                    content = content.split('```')[1]
                    if content.startswith('json'):
                        content = content[4:]
                    content = content.strip()
                    # Remove closing ```
                    if content.endswith('```'):
                        content = content[:-3].strip()
                investigation = json.loads(content)
            else:
                investigation = content
                
            return {
                "success": True,
                "investigation": investigation,
                "raw_response": response
            }
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Failed to parse investigation: {str(e)}",
                "raw_response": response
            }
    
    def _extract_code(self, content: str) -> str:
        """Extract Python code from AI response, removing markdown formatting"""
        content = content.strip()
        
        # Remove markdown code blocks
        if '```python' in content:
            parts = content.split('```python')
            if len(parts) > 1:
                code = parts[1].split('```')[0]
                code = code.strip()
        elif '```' in content:
            parts = content.split('```')
            if len(parts) >= 3:
                code = parts[1]
                # Remove language identifier if present
                lines = code.split('\n')
                if lines[0].strip() in ['python', 'py']:
                    code = '\n'.join(lines[1:])
                code = code.strip()
        else:
            # If no code blocks, use as-is (might be plain code)
            code = content.strip()
        
        # Clean up encoding issues (garbled characters from API)
        # Replace common encoding artifacts with safe alternatives
        replacements = {
            'ΓåÆ': '-',  # Arrow symbol (replace with hyphen for safety)
            'Γåö': '-',
            '\u0080': '',  # Remove null bytes and control characters
            '\u0081': '',
            '\u0082': '',
            '\u0083': '',
            '\u0084': '',
            '\u0085': '',
            '\u0086': '',
            '\u0087': '',
            '\u0088': '',
            '\u0089': '',
            '\u008a': '',
            '\u008b': '',
            '\u008c': '',
            '\u008d': '',
            '\u008e': '',
            '\u008f': '',
        }
        
        for bad_char, good_char in replacements.items():
            code = code.replace(bad_char, good_char)
        
        # Remove Nabu signature line that gets appended to code
        if 'This response was generated by Nabu.' in code:
            code = code.replace('This response was generated by Nabu.', '')
        
        # Remove any trailing non-code text after the last complete statement
        lines = code.split('\n')
        # Find last non-empty line that looks like code
        last_code_line = len(lines) - 1
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            if line and not line.startswith('#') and not line.startswith('This response'):
                last_code_line = i
                break
        code = '\n'.join(lines[:last_code_line + 1])
        
        # Remove import statements (they're already provided in sandbox)
        # The sandbox pre-imports: plotly.express, plotly.graph_objects, pandas, numpy
        cleaned_lines = []
        for line in code.split('\n'):
            stripped = line.strip()
            # Skip import lines for modules that are already available
            if stripped.startswith('import plotly') or \
               stripped.startswith('import pandas') or \
               stripped.startswith('import numpy') or \
               stripped.startswith('from plotly') or \
               stripped.startswith('from pandas') or \
               stripped.startswith('from numpy'):
                continue
            # Skip fig.show() calls (sandbox returns fig automatically)
            if stripped == 'fig.show()' or stripped.startswith('fig.show('):
                continue
            cleaned_lines.append(line)
        code = '\n'.join(cleaned_lines)
        
        return code.strip()


# Singleton instance
_nabu_client: Optional[NabuClient] = None


def get_nabu_client(api_token: str) -> NabuClient:
    """Get or create Nabu client instance"""
    global _nabu_client
    if _nabu_client is None:
        _nabu_client = NabuClient(api_token)
    return _nabu_client
