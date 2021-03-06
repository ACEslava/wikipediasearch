from datetime import datetime, timedelta

import asyncio
import discord
import os
import requests
from requests.models import HTTPError
import yaml
from discord.ext import commands
from pytube import YouTube as YoutubeDownload
from youtube_search import YoutubeSearch as YTSearch
from urllib import error as URLError
from src.loadingmessage import get_loading_message
from src.utils import error_handler


class YoutubeSearch:
    @staticmethod
    async def search(
        bot: commands.Bot,
        ctx: commands.Context,
        message: discord.Message,
        search_query: str,
        user_settings: dict,
    ) -> None:
        def result_embed(result_) -> discord.Embed:
            embed_ = discord.Embed(
                title=result_["title"],
                description=result_["long_desc"]
                if "long_desc" in result_.keys()
                else "No Description",
                url=f"https://www.youtube.com{result_['url_suffix']}",
            )
            embed_.add_field(name="Channel", value=result_["channel"], inline=True)
            embed_.add_field(name="Duration", value=result_["duration"], inline=True)
            embed_.add_field(name="Views", value=result_["views"], inline=True)
            embed_.add_field(
                name="Publish Time", value=result_["publish_time"], inline=True
            )

            embed_.set_thumbnail(url=result_["thumbnails"][0])
            embed_.set_footer(text=f"Requested by {ctx.author}")
            return embed_
        
        def download_embed(result_) -> discord.Embed:
            return discord.Embed(
                title=f"Available Videos",
                description="\n".join(
                    [f"[{index_}]: {value.resolution}, {round(value.filesize_approx/1000000, 2)}MB" for index_, value in enumerate(result_)]
                ),
            )

        try:
            result = YTSearch(search_query, max_results=10).to_dict()

            embeds = list(map(result_embed, result))

            do_exit, cur_page = False, 0
            await message.add_reaction("🗑️")
            await message.add_reaction("⬇️")
            if len(embeds) > 1:
                await message.add_reaction("◀️")
                await message.add_reaction("▶️")
            elif len(embeds) == 0:
                embed = discord.Embed(
                    description=f"No results found for: {search_query}"
                )
                await message.edit(content=None, embed=embed)
                await asyncio.sleep(60)
                await message.delete()
                return
            
            while not do_exit:
                try:
                    await message.edit(
                        content=None, embed=embeds[cur_page % len(embeds)]
                    )
                    reaction, user = await bot.wait_for(
                        "reaction_add",
                        check=lambda reaction_, user_: all(
                            [
                                str(reaction_.emoji) in ["◀️", "▶️", "🗑️", "⬇️"],
                                reaction_.message == message,
                                not user_.bot,
                            ]
                        ),
                        timeout=60,
                    )
                    await message.remove_reaction(reaction, user)
                    if str(reaction.emoji) == "🗑️":
                        await message.delete()
                        do_exit = True
                    elif str(reaction.emoji) == "◀️":
                        cur_page -= 1
                    elif str(reaction.emoji) == "▶️":
                        cur_page += 1
                    elif (
                        str(reaction.emoji) == "⬇️"
                        and user_settings[user.id]["downloadquota"]["dailyDownload"]
                        < 50
                    ):
                        await message.remove_reaction(reaction, bot.user)
                        msg = [await ctx.send(
                            f"{get_loading_message()}"
                        )]
                        yt = YoutubeDownload(embeds[cur_page].url)

                        download = yt.streams.filter(file_extension='mp4', progressive=True).order_by('resolution').fmt_streams
                        download = [vid for vid in download if round(vid.filesize_approx / 1000000, 2) < 100]
                        if len(download) != 0:
                            while 1:
                                download = [download[x : x + 10] for x in range(0, len(download), 10)] 
                                embeds = list(map(download_embed, download))
                                cur_page = 0

                                for index, item in enumerate(embeds):
                                    item.set_footer(
                                        text=f"Page {index+1}/{len(embeds)}\nRequested by: {str(ctx.author)}"
                                    )

                                await msg[0].add_reaction("🗑️")
                                if len(embeds) > 1:
                                    await msg[0].add_reaction("◀️")
                                    await msg[0].add_reaction("▶️")
                                msg.append(await ctx.send("Please choose option or cancel"))

                                while 1:
                                    await msg[0].edit(
                                        content=None, embed=embeds[cur_page % len(embeds)]
                                    )
                                    emojitask = asyncio.create_task(
                                        bot.wait_for(
                                            "reaction_add",
                                            check=lambda reaction_, user_: all(
                                                [
                                                    user_ == ctx.author,
                                                    str(reaction_.emoji) in ["◀️", "▶️", "🗑️"],
                                                    reaction_.message == msg[0],
                                                ]
                                            ),
                                            timeout=60,
                                        )
                                    )
                                    responsetask = asyncio.create_task(
                                        bot.wait_for(
                                            "message",
                                            check=lambda m: m.author == ctx.author,
                                            timeout=30,
                                        )
                                    )

                                    waiting = [emojitask, responsetask]
                                    done, waiting = await asyncio.wait(
                                        waiting, return_when=asyncio.FIRST_COMPLETED
                                    )  # 30 seconds wait either reply or react
                                    if emojitask in done:
                                        reaction, user = emojitask.result()
                                        await msg[0].remove_reaction(reaction, user)

                                        if str(reaction.emoji) == "🗑️":
                                            await msg[0].delete()
                                            return
                                        elif str(reaction.emoji) == "◀️":
                                            cur_page -= 1
                                        elif str(reaction.emoji) == "▶️":
                                            cur_page += 1

                                    elif responsetask in done:
                                        try:
                                            try:
                                                emojitask.cancel()
                                                input = responsetask.result()
                                                await input.delete()
                                                if input.content.lower() == "cancel":
                                                    raise UserCancel

                                                input = int(input.content)

                                            except ValueError or IndexError:
                                                await msg[-1].edit(
                                                    content="Invalid choice. Please choose a number between 0-9 or cancel"
                                                )
                                                continue

                                            try:
                                                for message in msg: await message.delete()
                                                msg = [await ctx.send(f"{get_loading_message()}")]
                                                download = download[cur_page][input]

                                                user_settings[user.id]["downloadquota"]["dailyDownload"] += round(download.filesize_approx / 1000000, 2)
                                                user_settings[user.id]["downloadquota"]["lifetimeDownload"] += round(download.filesize_approx / 1000000, 2)
                                                download.download(output_path="./src/cache")

                                                best_server = requests.get(
                                                    url="https://api.gofile.io/getServer"
                                                ).json()["data"]["server"]

                                                with open(
                                                    f'{os.path.abspath(f"./src/cache/{download.default_filename}")}',
                                                    "rb",
                                                ) as f:
                                                    url = f"https://{best_server}.gofile.io/uploadFile"
                                                    params = {
                                                        "expire": round(
                                                            datetime.timestamp(
                                                                datetime.now() + timedelta(minutes=10)
                                                            )
                                                        )
                                                    }
                                                    share_link = requests.post(
                                                        url=url,
                                                        params=params,
                                                        files={
                                                            f'@{os.path.abspath(f"./src/cache/{download.default_filename}")}': f
                                                        },
                                                    ).json()["data"]["downloadPage"]

                                                os.remove(f"./src/cache/{download.default_filename}")
                                                embed = discord.Embed(
                                                    description=(
                                                        f"{share_link}\n\n"
                                                        "You now have "
                                                        f"{50 - round(user_settings[user.id]['downloadquota']['dailyDownload'], 3)}MB "
                                                        f"left in your daily quota."
                                                        "Negative values mean your daily quota for the next day will be subtracted."
                                                    )
                                                )
                                                embed.set_footer(text=f"Requested by {user}")
                                                for message in msg: await message.delete()
                                                await ctx.send(embed=embed)

                                                with open("userSettings.yaml", "w") as data:
                                                    yaml.dump(user_settings, data, allow_unicode=True)

                                                return
                                            except asyncio.TimeoutError:
                                                await msg[0].clear_reactions()
                                                return

                                        except UserCancel or asyncio.TimeoutError:
                                            for message in msg:
                                                await message.delete()
                                            return

                                        except asyncio.CancelledError:
                                            pass

                                        except Exception:
                                            for message in msg:
                                                await message.delete()
                                            raise

                        else:
                            embed = discord.Embed(
                                description=(
                                    f"{user}, "
                                    f"no videos are eligible to download due to maximum filesize constraints (100MB)"
                                )
                            )
                            await msg[0].edit(content=None, embed=embed)

                except asyncio.TimeoutError:
                    await message.clear_reactions()
                except asyncio.CancelledError:
                    pass

        except UserCancel:
            await ctx.send(f"Cancelled")

        except asyncio.TimeoutError:
            await ctx.send(f"Search timed out. Aborting")

        except Exception as e:
            await error_handler(bot, ctx, e, search_query)
        finally:
            return


class UserCancel(Exception):
    pass
