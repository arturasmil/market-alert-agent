#!/usr/bin/env python3
"""
Market Alert Agent - Monitors SEC EDGAR filings for unusual activity
Checks 8-K, 13D, 13G, and Form 4 filings, scores them, and sends Telegram alerts
"""

import os
import json
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
import logging
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FormType(Enum):
    """SEC Filing form types to monitor"""
    FORM_8K = "8-K"
    FORM_13D = "13D"
    FORM_13G = "13G"
    FORM_4 = "4"


class FilingScorer:
    """Scores filings based on unusual activity indicators"""
    
    # Scoring weights for different indicators
    FORM_WEIGHTS = {
        FormType.FORM_8K: 1.0,      # 8-K = Material events
        FormType.FORM_13D: 2.5,     # 13D = 5%+ ownership + intent
        FormType.FORM_13G: 1.5,     # 13G = 5%+ ownership (passive)
        FormType.FORM_4: 1.2,       # Form 4 = Insider transactions
    }
    
    # Keywords indicating high-impact items
    HIGH_IMPACT_KEYWORDS = {
        "bankruptcy": 3.0,
        "acquisition": 2.5,
        "merger": 2.5,
        "liquidation": 3.0,
        "fraud": 4.0,
        "restatement": 2.0,
        "sec investigation": 2.5,
        "delisting": 2.0,
        "restructuring": 1.5,
        "board change": 1.2,
        "material agreement": 1.5,
        "offering": 1.3,
        "debt": 1.2,
    }
    
    # Unusual transaction patterns for Form 4
    UNUSUAL_TRANSACTION_PATTERNS = {
        "large sale": 2.0,           # Director/officer selling significantly
        "large purchase": 1.5,       # Director/officer buying significantly
        "option exercise": 1.2,
        "restricted stock": 1.0,
    }

    @classmethod
    def score_filing(cls, filing: Dict[str, Any]) -> Tuple[float, List[str]]:
        """
        Score a filing based on unusual indicators
        
        Returns:
            Tuple of (score, list of reason strings)
        """
        score = 0.0
        reasons = []
        
        # Base score from form type
        form_type_str = filing.get("form", "").strip()
        try:
            form_type = FormType(form_type_str)
            base_score = cls.FORM_WEIGHTS[form_type]
            score += base_score
            reasons.append(f"Form type: {form_type_str}")
        except ValueError:
            logger.warning(f"Unknown form type: {form_type_str}")
            return 0.0, []
        
        # Check for high-impact keywords in filing content
        description = (filing.get("description", "") or "").lower()
        for keyword, weight in cls.HIGH_IMPACT_KEYWORDS.items():
            if keyword in description:
                score += weight
                reasons.append(f"Contains '{keyword}'")
        
        # Additional scoring for Form 4 specifics
        if form_type_str == "4":
            form_4_score, form_4_reasons = cls._score_form_4(filing)
            score += form_4_score
            reasons.extend(form_4_reasons)
        
        # Additional scoring for 13D (activist investing indicator)
        if form_type_str == "13D":
            if "intent" in description.lower() or "purpose" in description.lower():
                score += 1.5
                reasons.append("Contains intent/purpose disclosure (activist signal)")
        
        # Boost score if recent filing
        filing_date = filing.get("filing_date")
        if filing_date:
            try:
                date_obj = datetime.strptime(filing_date, "%Y-%m-%d")
                days_old = (datetime.now() - date_obj).days
                if days_old == 0:
                    score *= 1.5
                    reasons.append("Filed today")
                elif days_old <= 1:
                    score *= 1.2
                    reasons.append("Filed yesterday")
            except ValueError:
                pass
        
        return score, reasons

    @classmethod
    def _score_form_4(cls, filing: Dict[str, Any]) -> Tuple[float, List[str]]:
        """Score Form 4 insider transactions"""
        score = 0.0
        reasons = []
        
        transactions = filing.get("transactions", [])
        if not transactions:
            return score, reasons
        
        for transaction in transactions:
            # Score based on transaction value
            value = transaction.get("value", 0)
            shares = transaction.get("shares", 0)
            
            if shares > 100000:  # Large transaction threshold
                if "sale" in transaction.get("type", "").lower():
                    score += 2.0
                    reasons.append(f"Large sale: {shares:,} shares worth ~${value:,.0f}")
                elif "purchase" in transaction.get("type", "").lower():
                    score += 1.5
                    reasons.append(f"Large purchase: {shares:,} shares worth ~${value:,.0f}")
        
        return score, reasons


class SECFilingFetcher:
    """Fetches current filings from SEC EDGAR"""
    
    # SEC EDGAR API endpoint
    SEC_API_URL = "https://data.sec.gov/submissions"
    SEC_FILINGS_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
    
    # Rate limiting headers for SEC compliance
    HEADERS = {
        "User-Agent": "Market-Alert-Agent/1.0 (Contact: email@example.com)",
    }

    @classmethod
    def fetch_recent_filings(cls, days: int = 1) -> List[Dict[str, Any]]:
        """
        Fetch recent SEC filings
        
        Args:
            days: Number of days back to search
            
        Returns:
            List of filing dictionaries
        """
        filings = []
        form_types = [form.value for form in FormType]
        
        for form_type in form_types:
            logger.info(f"Fetching {form_type} filings from last {days} day(s)")
            try:
                form_filings = cls._fetch_form_type(form_type, days)
                filings.extend(form_filings)
            except Exception as e:
                logger.error(f"Error fetching {form_type} filings: {e}")
        
        return filings

    @classmethod
    def _fetch_form_type(cls, form_type: str, days: int) -> List[Dict[str, Any]]:
        """Fetch specific form type from SEC"""
        filings = []
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        params = {
            "action": "getcompany",
            "type": form_type,
            "dateb": end_date.strftime("%Y%m%d"),
            "owner": "exclude",
            "count": 100,
            "output": "json",
        }
        
        try:
            response = requests.get(
                cls.SEC_FILINGS_URL,
                params=params,
                headers=cls.HEADERS,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            filings_data = data.get("filings", [])
            
            for filing in filings_data:
                filing_date = filing.get("filingDate", "")
                if filing_date:
                    try:
                        date_obj = datetime.strptime(filing_date, "%Y-%m-%d")
                        if date_obj >= start_date:
                            processed_filing = {
                                "form": form_type,
                                "company": filing.get("companyName", "Unknown"),
                                "cik": filing.get("cik", ""),
                                "filing_date": filing_date,
                                "accession": filing.get("accessionNumber", ""),
                                "description": filing.get("description", ""),
                                "url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={filing.get('cik')}&type={form_type}",
                            }
                            filings.append(processed_filing)
                    except ValueError:
                        continue
            
            logger.info(f"Found {len(filings)} {form_type} filings in date range")
        except requests.RequestException as e:
            logger.error(f"Request error fetching {form_type}: {e}")
        
        return filings


class TelegramAlertSender:
    """Sends alerts via Telegram"""
    
    TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
    
    def __init__(self, bot_token: str, chat_id: str):
        """
        Initialize Telegram sender
        
        Args:
            bot_token: Telegram bot token from GitHub Secrets
            chat_id: Telegram chat ID from GitHub Secrets
        """
        self.bot_token = bot_token
        self.chat_id = chat_id

    def send_alert(self, title: str, message: str, score: float, reasons: List[str]) -> bool:
        """
        Send formatted alert to Telegram
        
        Args:
            title: Alert title
            message: Main message content
            score: Numerical score
            reasons: List of reason strings
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Format the message
            formatted_message = self._format_message(title, message, score, reasons)
            
            url = self.TELEGRAM_API_URL.format(token=self.bot_token)
            payload = {
                "chat_id": self.chat_id,
                "text": formatted_message,
                "parse_mode": "HTML",
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info(f"Alert sent successfully: {title}")
            return True
        except requests.RequestException as e:
            logger.error(f"Failed to send Telegram alert: {e}")
            return False

    @staticmethod
    def _format_message(title: str, message: str, score: float, reasons: List[str]) -> str:
        """Format message for Telegram with HTML markup"""
        emoji = "🚨" if score > 3.0 else "⚠️" if score > 2.0 else "📊"
        
        formatted = f"{emoji} <b>{title}</b>\n\n"
        formatted += f"{message}\n\n"
        formatted += f"<b>Score:</b> {score:.2f}\n"
        formatted += f"<b>Reasons:</b>\n"
        
        for reason in reasons:
            formatted += f"  • {reason}\n"
        
        formatted += f"\n<i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"
        
        return formatted


def main():
    """Main agent execution"""
    logger.info("Starting Market Alert Agent")
    
    # Get credentials from environment
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        logger.error("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID environment variables")
        return False
    
    # Initialize components
    fetcher = SECFilingFetcher()
    scorer = FilingScorer()
    sender = TelegramAlertSender(bot_token, chat_id)
    
    # Fetch recent filings
    logger.info("Fetching recent SEC filings")
    filings = fetcher.fetch_recent_filings(days=1)
    
    if not filings:
        logger.info("No filings found in the last day")
        return True
    
    logger.info(f"Processing {len(filings)} filings")
    
    # Score and filter filings
    alerts_sent = 0
    alert_threshold = 1.5  # Minimum score to trigger alert
    
    # Sort by score descending
    scored_filings = []
    for filing in filings:
        score, reasons = scorer.score_filing(filing)
        if score > 0:
            scored_filings.append((score, filing, reasons))
    
    scored_filings.sort(key=lambda x: x[0], reverse=True)
    
    # Send alerts for top filings
    for score, filing, reasons in scored_filings[:10]:  # Top 10 filings
        if score >= alert_threshold:
            company = filing.get("company", "Unknown Company")
            form = filing.get("form", "Unknown")
            filing_date = filing.get("filing_date", "Unknown Date")
            
            title = f"{company} - {form} Filing"
            message = f"New SEC filing detected\n"
            message += f"<b>Company:</b> {company}\n"
            message += f"<b>Form:</b> {form}\n"
            message += f"<b>Date:</b> {filing_date}\n"
            message += f"<b>Link:</b> <a href='{filing.get('url', '#')}'>View on SEC EDGAR</a>"
            
            if sender.send_alert(title, message, score, reasons):
                alerts_sent += 1
        else:
            logger.debug(f"Filing score {score} below threshold {alert_threshold}")
    
    logger.info(f"Market Alert Agent completed. Sent {alerts_sent} alerts")
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
