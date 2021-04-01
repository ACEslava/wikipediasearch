import discord
import asyncio
from src.log import commandlog
import json

class Sudo:
    def __init__(
        self,
        bot,
        ctx):

        self.bot = bot
        self.ctx = ctx

        #Reads settings of server
        with open('serverSettings.json', 'r') as data:
            self.serverSettings = json.load(data)

    @staticmethod
    def settingsCheck(serverSettings, serverID):
        serverID = str(serverID)
        if serverID not in serverSettings.keys():
            serverSettings[serverID] = {}
        if 'blacklist' not in serverSettings[serverID].keys():
            serverSettings[serverID]['blacklist'] = []
        if 'commandprefix' not in serverSettings[serverID].keys():
            serverSettings[serverID]['commandprefix'] = '&'
        if 'adminrole' not in serverSettings[serverID].keys():
            serverSettings[serverID]['adminrole'] = None
        if 'sudoer' not in serverSettings[serverID].keys():
            serverSettings[serverID]['sudoer'] = []
        if 'safesearch' not in serverSettings[serverID].keys():
            serverSettings[serverID]['safesearch'] = False
        for searchEngines in ['wikipedia', 'scholar', 'google', 'mal', 'youtube']:
            if searchEngines not in serverSettings[serverID].keys():
                serverSettings[serverID][searchEngines] = True
        
        with open('serverSettings.json', 'w') as data:
            data.write(json.dumps(serverSettings, indent=4))
        return

    async def say(self, args):
        isOwner = await self.bot.is_owner(self.ctx.author)
        if isOwner == True and "--channel" in args:
            channel = int(args[args.index("--channel")+1])
            channel = await self.bot.fetch_channel(channel)
        elif "--channel" in args:
            channel = int(args[args.index("--channel")+1]) #Prevents non-owner sudoers from using bot in other servers
            channel = self.ctx.guild.get_channel(channel)

        if "--channel" in args:
                args.pop(args.index("--channel")+1)
                args.pop(args.index("--channel"))
                await channel.send(' '.join(args[1:]).strip())
        else: await self.ctx.send(' '.join(args[1:]).strip())

        return
    
    async def blacklist(self, args):
        if 'blacklist' not in self.serverSettings[str(self.ctx.guild.id)].keys():
            self.serverSettings[str(self.ctx.guild.id)]['blacklist'] = []

        if len(args) > 1:
            self.serverSettings[str(self.ctx.guild.id)]['blacklist'].append(str(args[1]))
            userinfo = await self.bot.fetch_user(int(args[1]))
            await self.ctx.send(f"'{str(userinfo)}' blacklisted")
        return
    
    async def whitelist(self, args):
        if 'blacklist' not in self.serverSettings[str(self.ctx.guild.id)].keys():
            self.serverSettings[str(self.ctx.guild.id)]['blacklist'] = []

        if len(args) > 1:
            try:
                self.serverSettings[str(self.ctx.guild.id)]['blacklist'].remove(str(args[1]))
                userinfo = await self.bot.fetch_user(int(args[1]))
                await self.ctx.send(f"'{str(userinfo)}' removed from blacklist")
            except ValueError:
                userinfo = await self.bot.fetch_user(int(args[1]))
                await self.ctx.send(f"'{str(userinfo)}' not in blacklist")
        return

    async def sudoer(self, args):
        if 'sudoer' not in self.serverSettings[str(self.ctx.guild.id)].keys():
            self.serverSettings[str(self.ctx.guild.id)]['sudoer'] = []

        if args[1] not in self.serverSettings[str(self.ctx.guild.id)]['sudoer']:
            self.serverSettings[str(self.ctx.guild.id)]['sudoer'].append(args[1])
            sudoerName = await self.bot.fetch_user(int(args[1]))
            await self.ctx.send(f"'{str(sudoerName)}' is now a sudoer")
        else: 
            sudoerName = await self.bot.fetch_user(int(args[1]))
            await self.ctx.send(f"'{str(sudoerName)}' is already a sudoer")
        return
    
    async def unsudoer(self, args):
        if 'sudoer' not in self.serverSettings[str(self.ctx.guild.id)].keys():
            self.serverSettings[str(self.ctx.guild.id)]['sudoer'] = []

        if args[1] in self.serverSettings[str(self.ctx.guild.id)]['sudoer']: 
            self.serverSettings[str(self.ctx.guild.id)]['sudoer'].remove(args[1])
            sudoerName = await self.bot.fetch_user(int(args[1]))
            await self.ctx.send(f"'{str(sudoerName)}' has been removed from sudo")
        else: 
            sudoerName = await self.bot.fetch_user(int(args[1]))
            await self.ctx.send(f"'{str(sudoerName)}' is not a sudoer")
        return
    
    async def config(self, args):
        def check(reaction, user):
            return user == self.ctx.author and str(reaction.emoji) in ['✅', '❌']
        adminrole = self.serverSettings[str(self.ctx.guild.id)]['adminrole']
        if adminrole != None:
            adminrole = self.ctx.guild.get_role(int(adminrole)) 
        if len(args) == 0:
            embed = discord.Embed(title="Guild Configuration")
            embed.add_field(name="Administration", value=f"""
` Adminrole:` {adminrole.name if adminrole != None else 'None set'}
`Safesearch:` {'✅' if self.serverSettings[str(self.ctx.guild.id)]['safesearch'] == True else '❌'}
`     Prefix:` {self.serverSettings[str(self.ctx.guild.id)]['commandprefix']}""")
            embed.add_field(name="Search Engines", value=f"""
`Wikipedia:` {'✅' if self.serverSettings[str(self.ctx.guild.id)]['wikipedia'] == True else '❌'}
`  Scholar:` {'✅' if self.serverSettings[str(self.ctx.guild.id)]['scholar'] == True else '❌'}
`   Google:` {'✅' if self.serverSettings[str(self.ctx.guild.id)]['google'] == True else '❌'}
`      MAL:` {'✅' if self.serverSettings[str(self.ctx.guild.id)]['mal'] == True else '❌'}
`  Youtube:` {'✅' if self.serverSettings[str(self.ctx.guild.id)]['youtube'] == True else '❌'}""")
            
            embed.set_footer(text=f"Requested by {self.ctx.author}")
            await self.ctx.send(embed=embed)
        elif args[0].lower() in ['wikipedia', 'scholar', 'google', 'myanimelist', 'youtube', 'safesearch']:
            embed = discord.Embed(title=args[0].capitalize(), description=f"{'✅' if self.serverSettings[str(self.ctx.guild.id)]['youtube'] == True else '❌'}")
            embed.set_footer(text=f"React with ✅/❌ to enable/disable")
            message = await self.ctx.send(embed=embed)
            try:
                await message.add_reaction('✅')
                await message.add_reaction('❌')

                reaction, user = await self.bot.wait_for("reaction_add", check=check, timeout=60)
                if str(reaction.emoji) == '✅':
                    self.serverSettings[str(self.ctx.guild.id)][args[0].lower()] = True
                elif str(reaction.emoji) == '❌':
                    self.serverSettings[str(self.ctx.guild.id)][args[0].lower()] = False
                await message.delete()
                await self.ctx.send(f"{args[0].capitalize()} is {'enabled' if self.serverSettings[str(self.ctx.guild.id)][args[0].lower()] == True else 'disabled'}")
                return
            except asyncio.TimeoutError as e: 
                await message.clear_reactions()
        elif args[0].lower() == 'adminrole':
            embed = discord.Embed(title='Adminrole', description=f"{await self.ctx.guild.get_role(int(adminrole)) if adminrole != None else 'None set'}")
            embed.set_footer(text=f"Reply with the roleID of the role you want to set")
            message = await self.ctx.send(embed=embed)

            try: 
                userresponse = await self.bot.wait_for('message', check=lambda m: m.author == self.ctx.author, timeout=30)
                await userresponse.delete()
                await message.delete()

                self.serverSettings[str(self.ctx.guild.id)]['adminrole'] = userresponse.content
                adminrole = self.ctx.guild.get_role(int(userresponse.content))
                await self.ctx.send(f"'{adminrole.name}' is now the admin role")
                return

            except asyncio.TimeoutError as e:
                return
        
        elif args[0].lower() == 'prefix':
            embed = discord.Embed(title='Prefix', description=f"{self.serverSettings[str(self.ctx.guild.id)]['commandprefix']}")
            embed.set_footer(text=f"Reply with the prefix that you want to set")
            message = await self.ctx.send(embed=embed)

            try: 
                userresponse = await self.bot.wait_for('message', check=lambda m: m.author == self.ctx.author, timeout=30)
                await userresponse.delete()
                await message.delete()

                self.serverSettings[str(self.ctx.guild.id)]['commandprefix'] = userresponse.content
                await self.ctx.send(f"'{userresponse.content}' is now the guild prefix")
                return

            except asyncio.TimeoutError as e:
                return
            
    
    async def sudo(self, args):
    
        #Checks if sudoer is owner
        isOwner = await self.bot.is_owner(self.ctx.author) 
        
        #Checks if sudoer is server owner
        if self.ctx.guild:
            isServerOwner = bool(self.ctx.author.id == self.ctx.guild.owner_id)
        else: isServerOwner = False

        #Checks if sudoer has the designated adminrole or is a sudoer
        try:
            hasAdmin = bool(self.serverSettings[str(self.ctx.guild.id)]['adminrole'] in [str(role.id) for role in self.ctx.author.roles])
            isSudoer = bool(str(self.ctx.author.id) in self.serverSettings[str(self.ctx.guild.id)]['sudoer'])
        except: pass
        
        if isOwner or isServerOwner or hasAdmin or isSudoer:
            if not args:
                await self.ctx.send("""
We trust you have received the usual lecture from the local System Administrator. It usually boils down to these three things:
#1) Respect the privacy of others.
#2) Think before you type.
#3) With great power comes great responsibility.
                """)
            elif args[0] == 'say':
                await self.say(args)
            elif args[0] == 'blacklist':
                await self.blacklist(args)
            elif args[0] == 'whitelist':
                await self.whitelist(args)
            elif args[0] == 'sudoer':
                await self.sudoer(args)
            elif args[0] == 'unsudoer':
                await self.unsudoer(args)
            elif args[0] == 'safesearch':
                await self.safesearch(args)
            elif args[0] == 'config':
                del args[0]
                await self.config(args)
            elif args[0]:
                await self.ctx.send(f"'{args[0]}' is not a valid command.")

            if args:
                log = commandlog(self.ctx, "sudo", ' '.join(args).strip())
                log.appendToLog()
                
        else: 
            await self.ctx.send(f"{self.ctx.author} is not in the sudoers file.  This incident will be reported.")
            log = commandlog(self.ctx, "sudo", 'unauthorised')
            log.appendToLog()

        with open('serverSettings.json', 'w') as data:
            data.write(json.dumps(self.serverSettings, indent=4))
        return