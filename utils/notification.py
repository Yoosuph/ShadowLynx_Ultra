import logging
import asyncio
import os
import json
import aiohttp
from typing import Dict, List, Optional, Any, Union

logger = logging.getLogger(__name__)

class NotificationService:
    """
    Service for sending alerts and notifications via Telegram and Discord
    """
    
    def __init__(self, telegram_token: Optional[str] = None, 
                 telegram_chat_id: Optional[str] = None,
                 discord_webhook: Optional[str] = None):
        """
        Initialize the NotificationService
        
        Args:
            telegram_token: Telegram bot token
            telegram_chat_id: Telegram chat ID
            discord_webhook: Discord webhook URL
        """
        self.telegram_token = telegram_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = telegram_chat_id or os.environ.get("TELEGRAM_CHAT_ID")
        self.discord_webhook = discord_webhook or os.environ.get("DISCORD_WEBHOOK")
        
        # Track notifications to avoid spamming
        self.recent_notifications = {}
        self.notification_cooldown = int(os.environ.get("NOTIFICATION_COOLDOWN_SECONDS", "300"))
        
        # Initialize notification levels
        self.notification_levels = {
            "low": 0,
            "medium": 1,
            "high": 2,
            "critical": 3
        }
        
        self.min_notification_level = os.environ.get("MIN_NOTIFICATION_LEVEL", "medium")
        
        logger.info(f"Notification service initialized. Telegram: {'Configured' if self.telegram_token else 'Not configured'}, "
                   f"Discord: {'Configured' if self.discord_webhook else 'Not configured'}")
        
    async def send_alert(self, message: str, priority: str = "medium", 
                         details: Optional[Dict] = None, deduplicate_key: Optional[str] = None) -> bool:
        """
        Send alert to configured notification channels
        
        Args:
            message: Alert message
            priority: Priority level (low, medium, high, critical)
            details: Additional details for the message
            deduplicate_key: Optional key for deduplication
            
        Returns:
            Success status
        """
        # Check if message should be sent based on priority
        if self.notification_levels.get(priority.lower(), 0) < self.notification_levels.get(self.min_notification_level, 0):
            logger.debug(f"Skipping notification with priority {priority} (below minimum {self.min_notification_level})")
            return False
            
        # Check for deduplication
        if deduplicate_key:
            import time
            current_time = time.time()
            
            if deduplicate_key in self.recent_notifications:
                last_time = self.recent_notifications[deduplicate_key]
                if current_time - last_time < self.notification_cooldown:
                    logger.debug(f"Skipping duplicate notification for key: {deduplicate_key}")
                    return False
                    
            self.recent_notifications[deduplicate_key] = current_time
            
            # Clean up old entries
            self.recent_notifications = {k: v for k, v in self.recent_notifications.items()
                                       if current_time - v < self.notification_cooldown * 2}
                                       
        # Format message with priority and details
        formatted_message = f"[{priority.upper()}] {message}"
        
        if details:
            formatted_message += "\n\nDetails:\n" + json.dumps(details, indent=2)
            
        # Send to all configured channels
        results = await asyncio.gather(
            self.send_telegram(formatted_message),
            self.send_discord(formatted_message, priority),
            return_exceptions=True
        )
        
        # Check results
        success = any([result is True for result in results if not isinstance(result, Exception)])
        
        if not success:
            logger.warning(f"Failed to send notification to any channel: {message}")
            
        return success
        
    async def send_telegram(self, message: str) -> bool:
        """
        Send message via Telegram
        
        Args:
            message: Message to send
            
        Returns:
            Success status
        """
        if not self.telegram_token or not self.telegram_chat_id:
            return False
            
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
                payload = {
                    "chat_id": self.telegram_chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }
                
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logger.debug("Telegram notification sent successfully")
                        return True
                    else:
                        response_text = await response.text()
                        logger.error(f"Failed to send Telegram notification: {response.status} - {response_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {str(e)}")
            return False
            
    async def send_discord(self, message: str, priority: str = "medium") -> bool:
        """
        Send message via Discord webhook
        
        Args:
            message: Message to send
            priority: Priority level for color coding
            
        Returns:
            Success status
        """
        if not self.discord_webhook:
            return False
            
        try:
            # Set color based on priority
            colors = {
                "low": 0x00FF00,      # Green
                "medium": 0xFFFF00,    # Yellow
                "high": 0xFF9900,      # Orange
                "critical": 0xFF0000   # Red
            }
            color = colors.get(priority.lower(), 0xFFFF00)
            
            async with aiohttp.ClientSession() as session:
                payload = {
                    "embeds": [{
                        "title": "ShadowLynx Ultra Alert",
                        "description": message,
                        "color": color,
                        "timestamp": datetime.datetime.utcnow().isoformat()
                    }]
                }
                
                async with session.post(self.discord_webhook, json=payload) as response:
                    if response.status == 204:
                        logger.debug("Discord notification sent successfully")
                        return True
                    else:
                        response_text = await response.text()
                        logger.error(f"Failed to send Discord notification: {response.status} - {response_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error sending Discord notification: {str(e)}")
            return False
            
    async def send_summary(self, title: str, data: Dict, priority: str = "low") -> bool:
        """
        Send a structured summary message
        
        Args:
            title: Summary title
            data: Dictionary of data to include in summary
            priority: Priority level
            
        Returns:
            Success status
        """
        # Format summary message
        message = f"<b>{title}</b>\n\n"
        
        for key, value in data.items():
            # Format key with snake_case to title Case
            formatted_key = " ".join(word.capitalize() for word in key.split('_'))
            
            # Format value based on type
            if isinstance(value, float):
                formatted_value = f"{value:.4f}"
            elif isinstance(value, dict):
                formatted_value = json.dumps(value, indent=2)
            else:
                formatted_value = str(value)
                
            message += f"<b>{formatted_key}:</b> {formatted_value}\n"
            
        return await self.send_alert(message, priority=priority)
