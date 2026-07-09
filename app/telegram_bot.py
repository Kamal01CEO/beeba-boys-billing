"""
Billing Software — Telegram Bot (Agent Interface)
Shop staff and owner can manage billing via Telegram.
"""
import logging
from typing import Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

logger = logging.getLogger(__name__)


class BillBot:
    """Telegram bot that acts as the AI agent interface for billing."""

    def __init__(
        self,
        token: str,
        sheets_manager,
        printer_manager=None,
        allowed_user_ids: list[int] = None,
        shop_name: str = "My Shop",
    ):
        self.token = token
        self.sheets = sheets_manager
        self.printer = printer_manager
        self.allowed_ids = set(allowed_user_ids or [])
        self.shop_name = shop_name
        self.application = None

    def _is_authorized(self, user_id: int) -> bool:
        if not self.allowed_ids:
            return True  # Allow all if no restriction set
        return user_id in self.allowed_ids

    def _auth_required(func):
        """Decorator for authorization check."""

        async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            if not update.effective_user:
                return
            if not self._is_authorized(update.effective_user.id):
                await update.message.reply_text("⛔ Unauthorized. Contact the shop owner.")
                return
            return await func(self, update, context, *args, **kwargs)
        return wrapper

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Welcome message."""
        await update.message.reply_text(
            f"🧾 *{self.shop_name} Billing Bot*\n\n"
            "I can help you manage billing. Try:\n\n"
            "📄 Create a bill:\n"
            "`/bill 1 Shirt=800, 1 Jeans=1500`\n\n"
            "💰 Check today's earnings:\n"
            "`/earnings` or `Today earnings`\n\n"
            "📋 Recent bills:\n"
            "`/recent` or `Last 5 bills`\n\n"
            "🔍 Search customer:\n"
            "`/search Ramesh`\n\n"
            "ℹ️ /help — All commands",
            parse_mode="Markdown",
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show all commands."""
        await update.message.reply_text(
            "📋 *All Commands:*\n\n"
            "`/bill 1 Shirt=800, 1 Jeans=1500`\n"
            "→ Generate bill with items\n\n"
            "`/earnings`\n"
            "→ Today's total earnings\n\n"
            "`/recent`\n"
            "→ Last 5 bills\n\n"
            "`/search Ramesh`\n"
            "→ Search bills by name/phone\n\n"
            "*Natural language:*\n"
            "• \"Today earnings\"\n"
            "• \"Last 5 bills\"\n"
            "• \"1 shirt=800, 1 jeans=1500\"\n\n"
            "When creating a bill, you'll be prompted for customer name, phone, and payment type.",
            parse_mode="Markdown",
        )

    async def bill_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create a bill from /bill command or natural language."""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            await update.message.reply_text("⛔ Unauthorized.")
            return

        text = update.message.text.strip()
        # Parse items from text like "1 Shirt=800, 1 Jeans=1500"
        items = self._parse_items(text)
        if not items:
            await update.message.reply_text(
                "❌ Could not parse items. Use format:\n"
                "`/bill 1 Shirt=800, 1 Jeans=1500`\n"
                "Or just type: `1 shirt=800, 1 jeans=1500`",
                parse_mode="Markdown",
            )
            return

        # Store in context for multi-step
        context.user_data["pending_items"] = items
        context.user_data["pending_total"] = sum(i["qty"] * i["price"] for i in items)

        total = context.user_data["pending_total"]
        items_summary = ", ".join(f"{i['qty']}x {i['name']}={i['price']}" for i in items)

        await update.message.reply_text(
            f"📝 *Items Entered:*\n{items_summary}\n\n"
            f"💵 *Total: Rs {total:.0f}*\n\n"
            "Now send me the *customer name* to continue.\n"
            "Or type `/cancel` to abort.",
            parse_mode="Markdown",
        )

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages — supports natural language and multi-step input."""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            return

        text = update.message.text.strip().lower()

        # Check for natural language commands
        if text in ("today earnings", "today earning", "earnings", "earning", "how much today"):
            await self._show_earnings(update)
            return

        if text in ("recent", "last 5", "last 5 bills", "recent bills"):
            await self._show_recent(update)
            return

        if text == "/cancel":
            context.user_data.clear()
            await update.message.reply_text("✅ Cancelled.")
            return

        # Handle multi-step bill creation flow
        if "pending_items" in context.user_data:
            await self._handle_bill_step(update, context, text)
            return

        # Try to parse as direct bill input (natural language)
        items = self._parse_items(update.message.text)
        if items:
            context.user_data["pending_items"] = items
            context.user_data["pending_total"] = sum(i["qty"] * i["price"] for i in items)
            total = context.user_data["pending_total"]
            items_summary = ", ".join(f"{i['qty']}x {i['name']}={i['price']}" for i in items)
            await update.message.reply_text(
                f"📝 *Items:* {items_summary}\n💵 *Total: Rs {total:.0f}*\n\nNow send me the *customer name*:",
                parse_mode="Markdown",
            )
            return

        await update.message.reply_text(
            "❓ Not sure what you mean. Try `/help` to see available commands.",
            parse_mode="Markdown",
        )

    async def _handle_bill_step(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Handle multi-step bill creation."""
        if "customer_name" not in context.user_data:
            context.user_data["customer_name"] = update.message.text.strip()
            await update.message.reply_text(
                f"👤 Customer: *{context.user_data['customer_name']}*\n\n"
                "Now send me the *phone number*:",
                parse_mode="Markdown",
            )
            return

        if "phone" not in context.user_data:
            context.user_data["phone"] = update.message.text.strip()
            await update.message.reply_text(
                f"📞 Phone: *{context.user_data['phone']}*\n\n"
                "Now select *payment type*:\n"
                "Type `Cash` or `UPI`",
                parse_mode="Markdown",
            )
            return

        if "payment_type" not in context.user_data:
            ptype = text.strip().title()
            if ptype not in ("Cash", "UPI"):
                await update.message.reply_text("❌ Invalid. Type `Cash` or `UPI`")
                return
            context.user_data["payment_type"] = ptype

            # All data collected — create the bill!
            await self._finalize_bill(update, context)

    async def _finalize_bill(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create the bill in Google Sheets and print."""
        try:
            data = context.user_data
            bill_no = self.sheets.add_bill(
                customer_name=data["customer_name"],
                phone=data["phone"],
                items=data["pending_items"],
                total=data["pending_total"],
                paid=data["pending_total"],
                payment_type=data["payment_type"],
            )

            # Try to print
            printed = False
            if self.printer:
                printed = self.printer.print_bill(
                    shop_name=self.shop_name,
                    shop_address="",
                    shop_contact="",
                    bill_no=bill_no,
                    customer_name=data["customer_name"],
                    phone=data["phone"],
                    items=data["pending_items"],
                    total=data["pending_total"],
                    paid=data["pending_total"],
                    payment_type=data["payment_type"],
                )

            items_summary = ", ".join(
                f"{i['qty']}x {i['name']}={i['price']}" for i in data["pending_items"]
            )

            msg = (
                f"✅ *Bill #{bill_no} Generated!*\n\n"
                f"👤 {data['customer_name']} — {data['phone']}\n"
                f"📦 {items_summary}\n"
                f"💵 Total: Rs {data['pending_total']:.0f}\n"
                f"💳 {data['payment_type']}\n"
            )
            if printed:
                msg += "🖨️ *Bill printed*"
            else:
                msg += "⚠️ Print skipped (no printer connected)"

            await update.message.reply_text(msg, parse_mode="Markdown")
            context.user_data.clear()

        except Exception as e:
            logger.error(f"Bill creation failed: {e}")
            await update.message.reply_text(f"❌ Failed to create bill: {e}")

    async def _show_earnings(self, update: Update):
        """Show today's earnings."""
        try:
            total = self.sheets.get_today_earnings()
            by_payment = self.sheets.get_today_earnings_by_payment()
            await update.message.reply_text(
                f"💰 *{self.shop_name} — Today's Earnings*\n\n"
                f"💵 Cash: Rs {by_payment.get('Cash', 0):.0f}\n"
                f"📱 UPI: Rs {by_payment.get('UPI', 0):.0f}\n"
                f"──────────────\n"
                f"*Total: Rs {total:.0f}*",
                parse_mode="Markdown",
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

    async def _show_recent(self, update: Update):
        """Show recent bills."""
        try:
            bills = self.sheets.get_recent_bills(5)
            if not bills:
                await update.message.reply_text("📭 No bills yet today.")
                return

            msg = f"📋 *{self.shop_name} — Recent Bills*\n\n"
            for b in bills:
                msg += (
                    f"`#{b['bill_no']}` {b['customer']} — "
                    f"Rs {b['total']} ({b['payment_type']})\n"
                )
            await update.message.reply_text(msg, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Search bills by customer name or phone."""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            await update.message.reply_text("⛔ Unauthorized.")
            return

        query = " ".join(context.args) if context.args else ""
        if not query:
            await update.message.reply_text("❌ Usage: `/search customer_name`")
            return

        try:
            results = self.sheets.search_bills(query)
            if not results:
                await update.message.reply_text(f"🔍 No bills found for '{query}'")
                return

            msg = f"🔍 *Search Results: '{query}'*\n\n"
            for b in results[:10]:
                msg += (
                    f"`#{b['bill_no']}` {b['customer']} — "
                    f"Rs {b['total']} ({b['payment_type']})\n"
                )
            await update.message.reply_text(msg, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

    async def recent_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Command handler for /recent."""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            await update.message.reply_text("⛔ Unauthorized.")
            return
        await self._show_recent(update)

    async def earnings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Command handler for /earnings."""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            await update.message.reply_text("⛔ Unauthorized.")
            return
        await self._show_earnings(update)

    def _parse_items(self, text: str) -> list[dict]:
        """Parse items from natural language text.
        
        Supports formats:
        - "1 Shirt=800, 1 Jeans=1500"
        - "1 shirt 800, 1 jeans 1500"
        - "shirt 800, jeans 1500" (qty defaults to 1)
        """
        items = []
        # Remove command prefix if present
        for prefix in ["/bill", "/b"]:
            if text.lower().startswith(prefix):
                text = text[len(prefix):].strip()
                break

        # Split by comma or newline
        parts = text.replace("\n", ",").split(",")
        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Pattern: "1 Shirt=800" or "1 Shirt 800" or "Shirt 800"
            import re
            match = re.match(r"(?:(\d+)\s+)?(.+?)\s*[=:\s]\s*(\d+(?:\.\d+)?)", part.strip())
            if match:
                qty = int(match.group(1)) if match.group(1) else 1
                name = match.group(2).strip().title()
                price = float(match.group(3))
                items.append({"name": name, "qty": qty, "price": price})

        return items

    def run(self):
        """Start the Telegram bot polling."""
        app = Application.builder().token(self.token).build()

        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("help", self.help))
        app.add_handler(CommandHandler("bill", self.bill_command))
        app.add_handler(CommandHandler("b", self.bill_command))
        app.add_handler(CommandHandler("earnings", self.earnings_command))
        app.add_handler(CommandHandler("recent", self.recent_command))
        app.add_handler(CommandHandler("search", self.search_command))

        # Text handler (natural language + multi-step)
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))

        logger.info("Telegram bot starting...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
