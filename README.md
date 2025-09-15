MIREA Lectures Bot (EOSO-01-25)

Quick start

1) System setup (Ubuntu):

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip ffmpeg fonts-dejavu-core
sudo apt install -y wkhtmltopdf
cd /root
mkdir -p /root/mirea-bot && cd /root/mirea-bot
cp -r /workspace/* .
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2) Environment

- Edit `.env` if needed (tokens, NextCloud creds already filled based on spec).

3) Run locally

```bash
source venv/bin/activate
python main.py
```

4) Systemd service

Create `/etc/systemd/system/mirea-bot.service`:

```ini
[Unit]
Description=MIREA Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/mirea-bot
Environment=PATH=/root/mirea-bot/venv/bin
ExecStart=/root/mirea-bot/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable mirea-bot
sudo systemctl start mirea-bot
sudo systemctl status mirea-bot -n 50 | cat
```

Notes

- Group chats: add the bot into the group, post any message to see the library pinned-by-recency (bot deletes previous library and reposts). Use the "Обновить" inline button to refresh.
- Private chat: use Start; buttons for Refresh, Add file; follow the flow for discipline -> upload -> lesson type -> topic.
- Audio: only first audio per session is used; others auto-dropped silently.
- Scan: in upload, choose "Скан" to send photos; upon "Готово" a PDF is built and added both to the lesson folder and discipline's conspects.
- Public links: NextCloud shares are created with edit rights for each discipline root.

Dependencies

- wkhtmltopdf is required for high-quality PDF rendering with MathJax support. If rendering fails, fallback text renderer is used.


  
# Solana-Mevbot
fully-automatic on-chain pump.fun solana MEVbot leveraging flashloans and the minimal gas fees of Solana to perform sandwich attacks and front-runs on https://pump.fun. 

> [!IMPORTANT]
> Due to the atomic nature of Flashloan operations, if they aren't profitable the transaction will revert and no net profit will be lost.

# Components

-- onchain solana program

-- website dashboard

# Operation
```mermaid
graph LR
A[MEVBOT] --Identify TX -->C(Mev Buy)--> E(Target Buy)
E --> F(Mev Sell)
F -->J(no arb)
J--tx reverted -->A
F --> H(arbitrage) --profit --> A
```
- The bot is constantly sniffing the https://pump.fun Solana master SPL for user buys, sells, and token creations containing slippage deficits.
> [!TIP]
> Bot operators can target any transaction value within their balance threshold. Generally, higher thresholds net consistently viable transactions
-  Once a transaction is identified, a flashloan is initiated for the target transaction amount, this requires a marginal amount of collateral.
-  The bot will aggresively attempt to front-run the transaction by dynamically monitoring the bribe to the miner and increasing it if necessary so as to be the first transaction mined.
- Depending on the set parameters, the bot will either front-run the Dev's sell to remain in profit, or sell upon the token reaching KOTH.
- The flashloan is then repaid, collateral is reiumbursed and profits are deposited into the operators wallet.
-  If the transaction is unprofitable at any point it will be reverted and the flashloan will be repaid, losing no gas or net profit.

# Setup
1. Download or clone the main branch of this repository

2. Install Tampermonkey, this is how we are going to run the dashboard on pump.fun

![c](https://i.imgur.com/gA2A7Zw.png)

3.  Deploy the program on Solana using the CLI and paste your MEVbot SPL address into the `program_address` variable.
> [!IMPORTANT]
>  skip this step if you want your dashboard to connect to my public MEV program for a .1% trading fee! 
4. Visit https://pump.fun

5. Open the Tampermonkey extension

![b](https://i.imgur.com/MjuX6v3.png)

6. Click `+ create new script`

![yy](https://i.postimg.cc/kMSpQ0x1/Screenshot-from-2024-09-17-01-38-19.png)

7. Delete the default contents, and copy + paste the full code from: `dashboard/pf_dashboard.js`

8. Save the file. The dashboard has now been installed.

9. Visit https://pump.fun and refresh the page. The dashboard should now be visible

10. Make sure your operator's wallet has 1.5 - 2 SOL for proper token acquisition and smooth operation. 

11. Click "START"

12. Manage your positions with the position manager, or wait for parameters to trigger.
    
![hj](https://i.postimg.cc/s2fkKTVB/Screenshot-from-2024-09-17-02-02-46.png)

14. Click STOP to stop the bot and close all positions at any time


> [!IMPORTANT]
> The bot will immediately begin searching for and transacting arbitrage on https://pump.fun

> [!TIP]
> Stop the bot any time by clicking the "STOP" button. any current transactions will be sold or reverted.

# Tips

- If the dashboard is enabled but not appearing; some chrome-based browsers must have developer mode enabled to support the TamperMonkey extension, you can find the toggle in the top right of the extensions page. 

- Increase the flashloan limit by .5 - 1 SOL if you wish to target more than one or two coins at a time.


# Contributions

Code contributions are welcome. If you would like to contribute please submit a pull request with your suggested changes.

# Support
If you benefitted from the project, show us some support by giving us a star ⭐. Help us pave the way for open-source!

# Help
If at any time you encounter any issues with the contract or dashboard setup, contact the team at https://t.me/solana_mevbot 🛡️
