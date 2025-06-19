import asyncio
import logging
import json
from typing import Dict, List, Optional
from datetime import datetime

import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "7927733051:AAF905Gywtotx__xP-ZsDCr7krkeCSE-n3g"
CLOUDFLARE_API_KEY = "8d6a11598d66525cba9755b5e822d9ba6dd1f"
CLOUDFLARE_EMAIL = "Gamerzbrutal65@gmail.com"
DOMAIN_NAME = "host-hunter.tech"
OWNER_ID = 6432580068

MAX_SUBDOMAINS = 50
SUPPORTED_TYPES = ["A", "AAAA", "CNAME"]

subdomain_stats = {"total_created": 0, "records": []}

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class CloudflareAPI:
    def __init__(self, api_key: str, email: str):
        self.api_key = api_key
        self.email = email
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.zone_id = None
    
    async def get_headers(self) -> Dict[str, str]:
        return {
            "X-Auth-Email": self.email,
            "X-Auth-Key": self.api_key,
            "Content-Type": "application/json"
        }
    
    async def get_zone_id(self, session: aiohttp.ClientSession) -> Optional[str]:
        """Fetch zone ID for the domain"""
        if self.zone_id:
            return self.zone_id
        
        url = f"{self.base_url}/zones"
        params = {"name": DOMAIN_NAME}
        headers = await self.get_headers()
        
        try:
            async with session.get(url, headers=headers, params=params) as response:
                data = await response.json()
                if data.get("success") and data.get("result"):
                    self.zone_id = data["result"][0]["id"]
                    return self.zone_id
                else:
                    logger.error(f"Failed to get zone ID: {data}")
                    return None
        except Exception as e:
            logger.error(f"Error getting zone ID: {e}")
            return None
    
    async def create_dns_record(self, session: aiohttp.ClientSession, name: str, 
                              record_type: str, content: str, ttl: int = 1) -> Dict:
        """Create DNS record"""
        zone_id = await self.get_zone_id(session)
        if not zone_id:
            return {"success": False, "error": "Could not get zone ID"}
        
        url = f"{self.base_url}/zones/{zone_id}/dns_records"
        headers = await self.get_headers()
        
        full_name = f"{name}.{DOMAIN_NAME}" if name != "@" else DOMAIN_NAME
        
        payload = {
            "type": record_type,
            "name": full_name,
            "content": content,
            "ttl": ttl,
            "proxied": False
        }
        
        try:
            async with session.post(url, headers=headers, json=payload) as response:
                data = await response.json()
                return data
        except Exception as e:
            logger.error(f"Error creating DNS record: {e}")
            return {"success": False, "error": str(e)}
    
    async def list_dns_records(self, session: aiohttp.ClientSession) -> List[Dict]:
        """List all DNS records for the domain"""
        zone_id = await self.get_zone_id(session)
        if not zone_id:
            return []
        
        url = f"{self.base_url}/zones/{zone_id}/dns_records"
        headers = await self.get_headers()
        
        try:
            async with session.get(url, headers=headers) as response:
                data = await response.json()
                if data.get("success"):
                    return data.get("result", [])
                return []
        except Exception as e:
            logger.error(f"Error listing DNS records: {e}")
            return []
    
    async def delete_dns_record(self, session: aiohttp.ClientSession, record_id: str) -> Dict:
        """Delete DNS record by ID"""
        zone_id = await self.get_zone_id(session)
        if not zone_id:
            return {"success": False, "error": "Could not get zone ID"}
        
        url = f"{self.base_url}/zones/{zone_id}/dns_records/{record_id}"
        headers = await self.get_headers()
        
        try:
            async with session.delete(url, headers=headers) as response:
                data = await response.json()
                return data
        except Exception as e:
            logger.error(f"Error deleting DNS record: {e}")
            return {"success": False, "error": str(e)}
    
    async def update_dns_record(self, session: aiohttp.ClientSession, record_id: str,
                              name: str, record_type: str, content: str, ttl: int = 1) -> Dict:
        """Update existing DNS record"""
        zone_id = await self.get_zone_id(session)
        if not zone_id:
            return {"success": False, "error": "Could not get zone ID"}
        
        url = f"{self.base_url}/zones/{zone_id}/dns_records/{record_id}"
        headers = await self.get_headers()
        
        full_name = f"{name}.{DOMAIN_NAME}" if name != "@" else DOMAIN_NAME
        
        payload = {
            "type": record_type,
            "name": full_name,
            "content": content,
            "ttl": ttl,
            "proxied": False
        }
        
        try:
            async with session.put(url, headers=headers, json=payload) as response:
                data = await response.json()
                return data
        except Exception as e:
            logger.error(f"Error updating DNS record: {e}")
            return {"success": False, "error": str(e)}

cf_api = CloudflareAPI(CLOUDFLARE_API_KEY, CLOUDFLARE_EMAIL)

def get_main_keyboard() -> InlineKeyboardMarkup:
    """Generate main menu keyboard"""
    keyboard = [
        [InlineKeyboardButton("🔨 CREATE", callback_data="action_create")],
        [InlineKeyboardButton("✏️ MODIFY", callback_data="action_modify")],
        [InlineKeyboardButton("🗑️ DELETE", callback_data="action_delete")],
        [InlineKeyboardButton("📋 LIST RECORDS", callback_data="action_list")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_record_type_keyboard() -> InlineKeyboardMarkup:
    """Generate record type selection keyboard"""
    keyboard = []
    for record_type in SUPPORTED_TYPES:
        keyboard.append([InlineKeyboardButton(record_type, callback_data=f"type_{record_type}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    welcome_text = f"""🌐 Welcome to Subdomain Maker Bot by @oceanhenter

**Domain:** `{DOMAIN_NAME}`
**Supported Types:** {', '.join(SUPPORTED_TYPES)}
**TTL:** Auto (1 = Auto)
**Proxy:** Off

✨ Fully Optimized
📊 Limit: {MAX_SUBDOMAINS} subdomains

Choose an option below:"""
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_keyboard(),
        parse_mode='Markdown'
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stats command - Owner only"""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ This command is only available for the bot owner.")
        return
    
    async with aiohttp.ClientSession() as session:
        records = await cf_api.list_dns_records(session)
        
    domain_records = [r for r in records if r['name'].endswith(f'.{DOMAIN_NAME}') or r['name'] == DOMAIN_NAME]
    
    stats_text = f"""📊 Subdomain Statistics

**Total Records:** {len(domain_records)}
**Created via Bot:** {subdomain_stats['total_created']}
**Domain:** `{DOMAIN_NAME}`

**Record Breakdown:**
"""
    
    type_count = {}
    for record in domain_records:
        record_type = record['type']
        type_count[record_type] = type_count.get(record_type, 0) + 1
    
    for record_type, count in type_count.items():
        stats_text += f"• {record_type}: {count}\n"
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "back_main":
        welcome_text = f"""🌐 Welcome to Subdomain Maker Bot by @oceanhenter

**Domain:** `{DOMAIN_NAME}`
**Supported Types:** {', '.join(SUPPORTED_TYPES)}
**TTL:** Auto (1 = Auto)
**Proxy:** Off

✨ Fully Optimized
📊 Limit: {MAX_SUBDOMAINS} subdomains

Choose an option below:"""
        
        await query.edit_message_text(
            welcome_text,
            reply_markup=get_main_keyboard(),
            parse_mode='Markdown'
        )
        
    elif data == "action_create":
        context.user_data['action'] = 'create'
        await query.edit_message_text(
            "🔨 CREATE SUBDOMAIN\n\nSelect record type:",
            reply_markup=get_record_type_keyboard(),
            parse_mode='Markdown'
        )
        
    elif data == "action_modify":
        context.user_data['action'] = 'modify'
        await show_records_for_modification(query, context)
        
    elif data == "action_delete":
        context.user_data['action'] = 'delete'
        await show_records_for_deletion(query, context)
        
    elif data == "action_list":
        await show_all_records(query, context)
        
    elif data.startswith("type_"):
        record_type = data.split("_")[1]
        context.user_data['record_type'] = record_type
        context.user_data['step'] = 'waiting_subdomain'
        
        await query.edit_message_text(
            f"🔨 CREATE {record_type} RECORD\n\n"
            f"Enter subdomain name (without .{DOMAIN_NAME}):\n"
            f"Example: `www` will create `www.{DOMAIN_NAME}`",
            parse_mode='Markdown'
        )
        
    elif data.startswith("delete_"):
        record_id = data.split("_")[1]
        await delete_record(query, context, record_id)
        
    elif data.startswith("modify_"):
        record_id = data.split("_")[1]
        context.user_data['modify_record_id'] = record_id
        await start_record_modification(query, context, record_id)

async def show_all_records(query, context):
    """Show all DNS records"""
    async with aiohttp.ClientSession() as session:
        records = await cf_api.list_dns_records(session)
    
    domain_records = [r for r in records if r['name'].endswith(f'.{DOMAIN_NAME}') or r['name'] == DOMAIN_NAME]
    
    if not domain_records:
        await query.edit_message_text(
            "📋 DNS RECORDS\n\nNo records found.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_main")]])
        )
        return
    
    text = "📋 DNS RECORDS\n\n"
    for record in domain_records[:20]:
        name = record['name'].replace(f'.{DOMAIN_NAME}', '') if record['name'] != DOMAIN_NAME else '@'
        text += f"• **{name}** ({record['type']}) → `{record['content']}`\n"
    
    if len(domain_records) > 20:
        text += f"\n... and {len(domain_records) - 20} more records"
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]),
        parse_mode='Markdown'
    )

async def show_records_for_deletion(query, context):
    """Show records for deletion"""
    async with aiohttp.ClientSession() as session:
        records = await cf_api.list_dns_records(session)
    
    domain_records = [r for r in records if r['name'].endswith(f'.{DOMAIN_NAME}') or r['name'] == DOMAIN_NAME]
    
    if not domain_records:
        await query.edit_message_text(
            "🗑️ DELETE RECORD\n\nNo records found to delete.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_main")]])
        )
        return
    
    keyboard = []
    for record in domain_records[:10]:
        name = record['name'].replace(f'.{DOMAIN_NAME}', '') if record['name'] != DOMAIN_NAME else '@'
        button_text = f"🗑️ {name} ({record['type']})"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"delete_{record['id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_main")])
    
    await query.edit_message_text(
        "🗑️ DELETE RECORD\n\nSelect record to delete:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_records_for_modification(query, context):
    """Show records for modification"""
    async with aiohttp.ClientSession() as session:
        records = await cf_api.list_dns_records(session)
    
    domain_records = [r for r in records if r['name'].endswith(f'.{DOMAIN_NAME}') or r['name'] == DOMAIN_NAME]
    
    if not domain_records:
        await query.edit_message_text(
            "✏️ MODIFY RECORD\n\nNo records found to modify.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_main")]])
        )
        return
    
    keyboard = []
    for record in domain_records[:10]:
        name = record['name'].replace(f'.{DOMAIN_NAME}', '') if record['name'] != DOMAIN_NAME else '@'
        button_text = f"✏️ {name} ({record['type']})"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"modify_{record['id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_main")])
    
    await query.edit_message_text(
        "✏️ MODIFY RECORD\n\nSelect record to modify:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def delete_record(query, context, record_id):
    """Delete a DNS record"""
    async with aiohttp.ClientSession() as session:
        result = await cf_api.delete_dns_record(session, record_id)
    
    if result.get('success'):
        await query.edit_message_text(
            "✅ Record deleted successfully!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Main", callback_data="back_main")]])
        )
    else:
        error_msg = result.get('error', 'Unknown error')
        await query.edit_message_text(
            f"❌ Failed to delete record\n\nError: {error_msg}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_main")]])
        )

async def start_record_modification(query, context, record_id):
    """Start record modification process"""
    async with aiohttp.ClientSession() as session:
        records = await cf_api.list_dns_records(session)
    
    record = next((r for r in records if r['id'] == record_id), None)
    if not record:
        await query.edit_message_text(
            "❌ Record not found.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_main")]])
        )
        return
    
    context.user_data['modify_record'] = record
    context.user_data['step'] = 'waiting_modify_content'
    
    name = record['name'].replace(f'.{DOMAIN_NAME}', '') if record['name'] != DOMAIN_NAME else '@'
    
    await query.edit_message_text(
        f"✏️ MODIFY RECORD\n\n"
        f"**Current:** {name} ({record['type']}) → `{record['content']}`\n\n"
        f"Enter new content for this record:",
        parse_mode='Markdown'
    )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages based on current step"""
    user_data = context.user_data
    step = user_data.get('step')
    
    if step == 'waiting_subdomain':
        subdomain = update.message.text.strip().lower()
        
        if not subdomain or any(c in subdomain for c in [' ', '.', '/', '\\']):
            await update.message.reply_text("❌ Invalid subdomain name. Please enter a valid subdomain (letters, numbers, hyphens only).")
            return
        
        user_data['subdomain'] = subdomain
        user_data['step'] = 'waiting_content'
        
        record_type = user_data['record_type']
        example = {
            'A': '192.168.1.1',
            'AAAA': '2001:db8::1',
            'CNAME': 'example.com'
        }.get(record_type, 'value')
        
        await update.message.reply_text(
            f"🎯 Enter {record_type} record content:\n\n"
            f"Example: `{example}`",
            parse_mode='Markdown'
        )
        
    elif step == 'waiting_content':
        content = update.message.text.strip()
        if not content:
            await update.message.reply_text("❌ Content cannot be empty.")
            return
        
        async with aiohttp.ClientSession() as session:
            records = await cf_api.list_dns_records(session)
        
        domain_records = [r for r in records if r['name'].endswith(f'.{DOMAIN_NAME}') or r['name'] == DOMAIN_NAME]
        
        if len(domain_records) >= MAX_SUBDOMAINS:
            await update.message.reply_text(f"❌ Maximum subdomain limit ({MAX_SUBDOMAINS}) reached.")
            user_data.clear()
            return
        
        subdomain = user_data['subdomain']
        record_type = user_data['record_type']
        
        async with aiohttp.ClientSession() as session:
            result = await cf_api.create_dns_record(session, subdomain, record_type, content)
        
        if result.get('success'):
            subdomain_stats['total_created'] += 1
            subdomain_stats['records'].append({
                'name': f"{subdomain}.{DOMAIN_NAME}",
                'type': record_type,
                'content': content,
                'created_at': datetime.now().isoformat()
            })
            
            await update.message.reply_text(
                f"✅ Record created successfully!\n\n"
                f"**Subdomain:** `{subdomain}.{DOMAIN_NAME}`\n"
                f"**Type:** {record_type}\n"
                f"**Content:** `{content}`\n"
                f"**TTL:** Auto\n"
                f"**Proxy:** Off",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard()
            )
        else:
            error_msg = result.get('errors', [{}])[0].get('message', 'Unknown error') if result.get('errors') else result.get('error', 'Unknown error')
            await update.message.reply_text(
                f"❌ Failed to create record\n\nError: {error_msg}",
                reply_markup=get_main_keyboard()
            )
        
        user_data.clear()
        
    elif step == 'waiting_modify_content':
        content = update.message.text.strip()
        if not content:
            await update.message.reply_text("❌ Content cannot be empty.")
            return
        
        record = user_data['modify_record']
        record_id = user_data['modify_record_id']
        
        name = record['name'].replace(f'.{DOMAIN_NAME}', '') if record['name'] != DOMAIN_NAME else '@'
        
        async with aiohttp.ClientSession() as session:
            result = await cf_api.update_dns_record(session, record_id, name, record['type'], content)
        
        if result.get('success'):
            await update.message.reply_text(
                f"✅ Record updated successfully!\n\n"
                f"**Subdomain:** `{record['name']}`\n"
                f"**Type:** {record['type']}\n"
                f"**New Content:** `{content}`",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard()
            )
        else:
            error_msg = result.get('errors', [{}])[0].get('message', 'Unknown error') if result.get('errors') else result.get('error', 'Unknown error')
            await update.message.reply_text(
                f"❌ Failed to update record\n\nError: {error_msg}",
                reply_markup=get_main_keyboard()
            )
        
        user_data.clear()

def main():
    """Start the bot"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    print("🚀 Bot starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
