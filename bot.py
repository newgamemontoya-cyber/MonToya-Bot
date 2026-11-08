import os
import sqlite3
import discord
from discord import app_commands
from discord.ext import commands

# Detectar si estamos en Render (Nube) o en la PC (Local)
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
  # Conexión para PostgreSQL en Render (Nube - Persistente)
  import psycopg2

  conn = psycopg2.connect(DATABASE_URL, sslmode="require")
  cursor = conn.cursor()
  is_postgres = True
else:
  # Conexión local para tu PC (SQLite)
  conn = sqlite3.connect("database.db")
  cursor = conn.cursor()
  is_postgres = False

# Crear la tabla según el tipo de base de datos
if is_postgres:
  cursor.execute(
      """
        CREATE TABLE IF NOT EXISTS customer_balances (
            user_id BIGINT PRIMARY KEY,
            balance REAL
        )
    """
  )
else:
  cursor.execute(
      """
        CREATE TABLE IF NOT EXISTS customer_balances (
            user_id INTEGER PRIMARY KEY,
            balance REAL
        )
    """
  )
conn.commit()

# 2. Configuración del Bot de Discord
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
  print(f"¡Bot conectado como {bot.user}!")
  try:
    synced = await bot.tree.sync()
    print(f"Se sincronizaron {len(synced)} comandos.")
  except Exception as e:
    print(e)


# Función auxiliar para guardar datos compatible con ambos sistemas
def guardar_balance(user_id, new_balance):
  if is_postgres:
    cursor.execute(
        """
            INSERT INTO customer_balances (user_id, balance) VALUES (%s, %s)
            ON CONFLICT (user_id) DO UPDATE SET balance = %s
        """,
        (user_id, new_balance, new_balance),
    )
  else:
    cursor.execute(
        """
            INSERT INTO customer_balances (user_id, balance) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET balance = ?
        """,
        (user_id, new_balance, new_balance),
    )
  conn.commit()


# 3. Comando Slash: /add_balance
@bot.tree.command(
    name="add_balance",
    description="Adds an amount to a customer's total spent balance.",
)
@app_commands.describe(
    customer="The customer user to add the balance to",
    amount="The money amount to add (e.g. 20.00)",
)
@app_commands.checks.has_permissions(administrator=True)
async def add_balance(
    interaction: discord.Interaction, customer: discord.Member, amount: float
):
  if amount <= 0:
    await interaction.response.send_message(
        "The amount must be greater than 0.", ephemeral=True
    )
    return

  user_id = customer.id

  if is_postgres:
    cursor.execute(
        "SELECT balance FROM customer_balances WHERE user_id = %s", (user_id,)
    )
  else:
    cursor.execute(
        "SELECT balance FROM customer_balances WHERE user_id = ?", (user_id,)
    )

  resultado = cursor.fetchone()
  previous_balance = resultado[0] if resultado else 0.0
  new_balance = previous_balance + amount

  guardar_balance(user_id, new_balance)

  embed = discord.Embed(
      title="🧾 MONTOYA SERVICES — PAYMENT RECORD",
      color=discord.Color.from_rgb(20, 110, 180),
  )

  embed.add_field(
      name="🛠️ Staff",
      value=f"{interaction.user.mention}\n`[{interaction.user.id}]`",
      inline=True,
  )
  embed.add_field(
      name="👤 Customer", value=f"{customer.mention}\n`[{customer.id}]`", inline=True
  )

  embed.add_field(name="💰 Amount Added", value=f"`+${amount:.2f}`", inline=False)
  embed.add_field(
      name="📊 Previous Balance",
      value=f"`${previous_balance:.2f}`",
      inline=False,
  )
  embed.add_field(
      name="📈 New Balance Total", value=f"`${new_balance:.2f}`", inline=False
  )

  embed.set_thumbnail(url=customer.display_avatar.url)
  embed.set_footer(
      text="MonToya Services • Payment System",
      icon_url=bot.user.avatar.url if bot.user.avatar else None,
  )

  await interaction.response.send_message(embed=embed)


# 4. Comando Slash: /remove_balance
@bot.tree.command(
    name="remove_balance",
    description="Removes an amount from a customer's total spent balance.",
)
@app_commands.describe(
    customer="The customer user to remove the balance from",
    amount="The money amount to remove (e.g. 20.00)",
)
@app_commands.checks.has_permissions(administrator=True)
async def remove_balance(
    interaction: discord.Interaction, customer: discord.Member, amount: float
):
  if amount <= 0:
    await interaction.response.send_message(
        "The amount must be greater than 0.", ephemeral=True
    )
    return

  user_id = customer.id

  if is_postgres:
    cursor.execute(
        "SELECT balance FROM customer_balances WHERE user_id = %s", (user_id,)
    )
  else:
    cursor.execute(
        "SELECT balance FROM customer_balances WHERE user_id = ?", (user_id,)
    )

  resultado = cursor.fetchone()
  previous_balance = resultado[0] if resultado else 0.0
  new_balance = max(0.0, previous_balance - amount)

  guardar_balance(user_id, new_balance)

  embed = discord.Embed(
      title="⚠️ MONTOYA SERVICES — BALANCE CORRECTION",
      color=discord.Color.from_rgb(215, 50, 50),
  )

  embed.add_field(
      name="🛠️ Staff",
      value=f"{interaction.user.mention}\n`[{interaction.user.id}]`",
      inline=True,
  )
  embed.add_field(
      name="👤 Customer", value=f"{customer.mention}\n`[{customer.id}]`", inline=True
  )

  embed.add_field(
      name="💸 Amount Removed", value=f"`-${amount:.2f}`", inline=False
  )
  embed.add_field(
      name="📊 Previous Balance",
      value=f"`${previous_balance:.2f}`",
      inline=False,
  )
  embed.add_field(
      name="📈 New Balance Total", value=f"`${new_balance:.2f}`", inline=False
  )

  embed.set_thumbnail(url=customer.display_avatar.url)
  embed.set_footer(
      text="MonToya Services • Correction System",
      icon_url=bot.user.avatar.url if bot.user.avatar else None,
  )

  await interaction.response.send_message(embed=embed)


# 5. Comando Slash: /check_balance
@bot.tree.command(
    name="check_balance", description="Check your total spent balance."
)
@app_commands.describe(
    customer="(Optional - Staff Only) The customer you want to check"
)
async def check_balance(
    interaction: discord.Interaction, customer: discord.Member = None
):
  if customer and customer.id != interaction.user.id:
    if not interaction.user.guild_permissions.administrator:
      await interaction.response.send_message(
          "❌ You can only check your own balance.", ephemeral=True
      )
      return
    target_user = customer
  else:
    target_user = interaction.user

  if is_postgres:
    cursor.execute(
        "SELECT balance FROM customer_balances WHERE user_id = %s",
        (target_user.id,),
    )
  else:
    cursor.execute(
        "SELECT balance FROM customer_balances WHERE user_id = ?",
        (target_user.id,),
    )

  resultado = cursor.fetchone()
  balance = resultado[0] if resultado else 0.0

  embed = discord.Embed(
      title=f"💳 Balance Information",
      color=discord.Color.from_rgb(40, 180, 99),
  )

  embed.add_field(
      name="👤 User", value=f"{target_user.mention}\n`[{target_user.id}]`", inline=False
  )
  embed.add_field(
      name="💵 Total Spent Balance", value=f"`${balance:.2f} USD`", inline=False
  )

  embed.set_thumbnail(url=target_user.display_avatar.url)
  embed.set_footer(
      text="MonToya Services • Balance Checker",
      icon_url=bot.user.avatar.url if bot.user.avatar else None,
  )

  await interaction.response.send_message(embed=embed)


# Arranque seguro con la variable de entorno para la nube
bot.run(os.environ["DISCORD_TOKEN"])
# Arranque del bot (recuerda usar tu token local o de entorno según prefieras)
bot.run(os.environ["DISCORD_TOKEN"])
