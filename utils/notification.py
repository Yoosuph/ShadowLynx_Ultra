import logging
import asyncio
import aiohttp
import json
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class NotificationService:
    """
    Service for sending notifications and alerts through various channels
    """
    
    def __init__(self, telegram_token: Optional[str] = None, 
                 telegram_chat_id: Optional[str] = None,
                 discord_webhook: Optional[str] = None):
        """
        Initialize the NotificationService
        
        Args:
            telegram_token: Telegram bot token
            telegram_chat_id: Telegram chat ID for sending messages
            discord_webhook: Discord webhook URL
        """
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.discord_webhook = discord_webhook
        
        # Track alert history
        self.recent_alerts = []
        self.max_history = 100
        
    async def send_alert(self, message: str, priority: str = "normal", 
                         data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send an alert through configured channels
        
        Args:
            message: Alert message
            priority: Priority level (low, normal, high)
            data: Optional additional data
            
        Returns:
            True if alert was sent successfully
        """
        # Add to history
        self.recent_alerts.append({
            "message": message,
            "priority": priority,
            "data": data
        })
        
        # Trim history
        if len(self.recent_alerts) > self.max_history:
            self.recent_alerts = self.recent_alerts[-self.max_history:]
            
        # Send through available channels
        success = False
        
        # Only send high priority alerts through external channels
        if priority == "high":
            # Telegram
            telegram_success = await self._send_telegram(message, data)
            
            # Discord
            discord_success = await self._send_discord(message, data)
            
            success = telegram_success or discord_success
            
        # Always log the alert
        if priority == "high":
            logger.warning(f"ALERT: {message}")
        else:
            logger.info(f"Notification: {message}")
            
        return success
    
    async def _send_telegram(self, message: str, 
                             data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send message through Telegram
        
        Args:
            message: Message text
            data: Optional additional data
            
        Returns:
            True if message was sent successfully
        """
        if not self.telegram_token or not self.telegram_chat_id:
            return False
            
        try:
            # Format message
            text = message
            if data:
                # Add formatted data if present
                text += "\n\n"
                text += json.dumps(data, indent=2)
                
            # Send message
            async with aiohttp.ClientSession() as session:
                url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
                params = {
                    "chat_id": self.telegram_chat_id,
                    "text": text,
                    "parse_mode": "Markdown"
                }
                
                async with session.post(url, params=params) as response:
                    if response.status == 200:
                        return True
                    else:
                        logger.warning(f"Telegram API error: {await response.text()}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error sending Telegram message: {str(e)}")
            return False
    
    async def _send_discord(self, message: str, 
                            data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send message through Discord webhook
        
        Args:
            message: Message text
            data: Optional additional data
            
        Returns:
            True if message was sent successfully
        """
        if not self.discord_webhook:
            return False
            
        try:
            # Format content
            content = {
                "content": message,
                "username": "ShadowLynx Arbitrage",
                "embeds": []
            }
            
            if data:
                # Add data as embed
                embed = {
                    "title": "Alert Details",
                    "color": 15258703,  # Red color
                    "fields": []
                }
                
                for key, value in data.items():
                    field = {
                        "name": key,
                        "value": str(value),
                        "inline": True
                    }
                    embed["fields"].append(field)
                    
                content["embeds"].append(embed)
                
            # Send message
            async with aiohttp.ClientSession() as session:
                async with session.post(self.discord_webhook, json=content) as response:
                    if response.status == 204:
                        return True
                    else:
                        logger.warning(f"Discord API error: {await response.text()}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error sending Discord message: {str(e)}")
            return False
            
    def get_recent_alerts(self, limit: int = 10, 
                          min_priority: str = "normal") -> list:
        """
        Get recent alerts from history
        
        Args:
            limit: Maximum number of alerts to return
            min_priority: Minimum priority level
            
        Returns:
            List of recent alerts
        """
        priority_levels = {"low": 0, "normal": 1, "high": 2}
        min_level = priority_levels.get(min_priority, 0)
        
        filtered_alerts = [
            alert for alert in self.recent_alerts
            if priority_levels.get(alert["priority"], 0) >= min_level
        ]
        
        return filtered_alerts[-limit:]