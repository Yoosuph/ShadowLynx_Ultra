import os
import json
import logging
from datetime import datetime, timedelta

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
from openai import OpenAI

logger = logging.getLogger(__name__)

class AIAgent:
    """
    Advanced AI Agent powered by OpenAI's GPT-4o model for blockchain arbitrage analysis
    and strategy optimization.
    """
    
    def __init__(self, api_key=None):
        """
        Initialize the AI Agent
        
        Args:
            api_key: OpenAI API key (optional, defaults to env var)
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("OpenAI API key not provided. AI Agent functionality will be limited.")
        
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None
        self.model = "gpt-4o"  # Using the latest model
        
    async def analyze_opportunity(self, opportunity_data):
        """
        Analyze an arbitrage opportunity and provide insights
        
        Args:
            opportunity_data: Dictionary with opportunity details
            
        Returns:
            Dictionary with analysis results
        """
        if not self.client:
            return {"error": "OpenAI API key not configured"}
        
        try:
            # Convert opportunity data to a consistent format
            opportunity_json = json.dumps(opportunity_data, indent=2)
            
            # Craft a detailed system prompt for accurate analysis
            system_prompt = """
            You are ShadowLynx AI, an expert blockchain arbitrage analysis system.
            Analyze the provided arbitrage opportunity and assess its:
            1. Probability of success
            2. Risk factors
            3. Recommended strategy
            4. Expected profitability impact
            
            Consider volatility, liquidity, gas costs, and potential market shifts.
            Respond with JSON that includes scoring and rationale in these fields:
            {"success_probability": FLOAT 0-1, "risk_score": FLOAT 0-10, "strategy_recommendation": STRING, "profitability_impact": STRING, "rationale": STRING}
            """
            
            user_prompt = f"""
            Analyze this arbitrage opportunity:
            {opportunity_json}
            
            Based on current blockchain arbitrage trends, known DEX behaviors, and market conditions,
            provide your assessment following the specified format.
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2,  # Lower temperature for more consistent responses
            )
            
            # Parse the response to ensure valid JSON
            result = json.loads(response.choices[0].message.content)
            
            # Add timestamp to the result
            result["timestamp"] = datetime.utcnow().isoformat()
            return result
            
        except Exception as e:
            logger.error(f"Error in AI opportunity analysis: {str(e)}")
            return {
                "error": str(e),
                "success_probability": 0.0,
                "risk_score": 10.0,
                "strategy_recommendation": "Unable to analyze due to error",
                "profitability_impact": "Unknown",
                "rationale": f"Analysis failed: {str(e)}"
            }
    
    async def generate_market_insights(self, token_pairs, timeframe="24h"):
        """
        Generate market insights for specific token pairs
        
        Args:
            token_pairs: List of token pairs to analyze
            timeframe: Timeframe for analysis (e.g., "24h", "7d")
            
        Returns:
            Dictionary with market insights
        """
        if not self.client:
            return {"error": "OpenAI API key not configured"}
        
        try:
            # Prepare token data for prompt
            token_list = ", ".join(token_pairs)
            
            system_prompt = """
            You are ShadowLynx AI, an expert in cryptocurrency market analysis.
            Provide detailed market insights for the specified tokens, focusing on:
            1. Current market trends
            2. Volatility analysis
            3. Liquidity patterns
            4. Cross-DEX arbitrage opportunities
            5. Short-term price predictions (next 24-48 hours)
            
            Base your analysis on the most recent trends in DeFi arbitrage and DEX trading.
            Structure your response as JSON with these fields:
            {"market_summary": STRING, "tokens": [{ANALYSIS PER TOKEN}], "arbitrage_opportunities": [OPPORTUNITIES], "recommendations": [LIST OF STRINGS]}
            """
            
            user_prompt = f"""
            Generate market insights for these token pairs: {token_list}
            Timeframe: {timeframe}
            
            Focus on potential arbitrage opportunities across Binance Smart Chain and Polygon networks.
            Provide actionable insights that would be valuable for a flash loan arbitrage system.
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=1500,
            )
            
            # Parse the response
            result = json.loads(response.choices[0].message.content)
            
            # Add timestamp and request details
            result["timestamp"] = datetime.utcnow().isoformat()
            result["tokens_analyzed"] = token_pairs
            result["timeframe"] = timeframe
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating market insights: {str(e)}")
            return {
                "error": str(e),
                "market_summary": "Unable to generate insights due to an error",
                "tokens": [],
                "arbitrage_opportunities": [],
                "recommendations": [f"API error occurred: {str(e)}"]
            }
    
    async def optimize_strategy(self, historical_data, current_params):
        """
        Optimize trading strategy based on historical performance
        
        Args:
            historical_data: Dictionary with historical trading data
            current_params: Current strategy parameters
            
        Returns:
            Dictionary with optimized strategy parameters
        """
        if not self.client:
            return {"error": "OpenAI API key not configured"}
        
        try:
            # Prepare data for prompt
            historical_json = json.dumps(historical_data, indent=2)
            params_json = json.dumps(current_params, indent=2)
            
            system_prompt = """
            You are ShadowLynx AI, a blockchain arbitrage strategy optimizer.
            Analyze the historical trading data and current strategy parameters to recommend
            optimized parameters that could improve profitability and reduce risk.
            
            Consider gas costs, success rates, token volatility, and market conditions.
            Your response should be JSON with these fields:
            {"optimized_parameters": {PARAM OBJECT}, "reasoning": {REASONING OBJECT WITH ONE ENTRY PER PARAMETER}, "expected_improvement": STRING}
            """
            
            user_prompt = f"""
            Historical trading data:
            {historical_json}
            
            Current strategy parameters:
            {params_json}
            
            Optimize these parameters to improve profitability while maintaining acceptable risk levels.
            Explain your reasoning for each parameter adjustment.
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=1000,
            )
            
            # Parse the response
            result = json.loads(response.choices[0].message.content)
            
            # Add timestamp
            result["timestamp"] = datetime.utcnow().isoformat()
            result["based_on_data_from"] = historical_data.get("period", "unknown period")
            
            return result
            
        except Exception as e:
            logger.error(f"Error optimizing strategy: {str(e)}")
            return {
                "error": str(e),
                "optimized_parameters": current_params,
                "reasoning": {"error": f"Optimization failed: {str(e)}"},
                "expected_improvement": "None - error occurred"
            }

    async def explain_opportunity(self, opportunity_data, technical_level="medium"):
        """
        Generate a human-readable explanation of an arbitrage opportunity
        
        Args:
            opportunity_data: Dictionary with opportunity details
            technical_level: How technical the explanation should be (basic, medium, expert)
            
        Returns:
            Dictionary with explanation text
        """
        if not self.client:
            return {"explanation": "AI explanation unavailable - API key not configured"}
        
        try:
            # Convert opportunity data to a consistent format
            opportunity_json = json.dumps(opportunity_data, indent=2)
            
            system_prompt = f"""
            You are ShadowLynx AI, an expert in explaining blockchain arbitrage concepts.
            Explain the provided arbitrage opportunity in {technical_level} technical language.
            
            Focus on:
            1. What arbitrage opportunity was identified
            2. How the flash loan process would work for this opportunity
            3. Why a profit can be made in this specific case
            4. What risks might be involved
            
            Make your explanation educational and clear, suitable for someone with a {technical_level} understanding of DeFi.
            """
            
            user_prompt = f"""
            Explain this arbitrage opportunity in detail:
            {opportunity_json}
            
            Provide a {technical_level}-level explanation that helps understand both the opportunity and the mechanics behind it.
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=800,
            )
            
            explanation = response.choices[0].message.content
            
            return {
                "explanation": explanation,
                "technical_level": technical_level,
                "opportunity_id": opportunity_data.get("id", "unknown"),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating explanation: {str(e)}")
            return {
                "explanation": f"Unable to generate explanation due to an error: {str(e)}",
                "technical_level": technical_level,
                "error": str(e)
            }