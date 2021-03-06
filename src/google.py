from asyncio import TimeoutError, gather
from base64 import standard_b64encode
from re import findall, sub, search
from string import ascii_uppercase, ascii_lowercase, digits
from typing import List

import discord
from bs4 import BeautifulSoup
from discord import Embed
from discord.ext import commands
from iso639 import languages
from langid import classify as detect
from requests import get
from translate import Translator

from src.utils import Log, error_handler
from src.loadingmessage import get_loading_message


class GoogleSearch:
    def __init__(
        self,
        bot: commands.Bot,
        ctx: commands.Context,
        server_settings: dict,
        user_settings: dict,
        message: discord.Message,
        search_query: str,
    ):
        self.bot = bot
        self.ctx = ctx
        self.serverSettings = server_settings
        self.userSettings = user_settings
        self.message = message
        self.search_query = search_query
        return

    async def search(self) -> None:
        # region utility functions

        # translates unicode codes in links
        def link_unicode_parse(link: str) -> str:
            return sub(r"%(.{2})", lambda m: chr(int(m.group(1), 16)), link)

        # formats uule strings for use in locales
        # found this on a random stackoverflow
        def uule(city: str) -> str:
            secret_list = (
                list(ascii_uppercase)
                + list(ascii_lowercase)
                + list(digits)
                + ["-", "_"]
            )

            secret = secret_list[len(city) % len(secret_list)]
            hashed = standard_b64encode(city.encode()).decode().strip("=")
            return f"w+CAIQICI{secret}{hashed}"

        # parses image url from html
        def image_url_parser(image) -> str:
            try:
                # searches html for image urls
                imgurl = link_unicode_parse(
                    findall(
                        "(?<=imgurl=).*(?=&imgrefurl)", image.parent.parent["href"]
                    )[0]
                )
                if "encrypted" in imgurl:
                    imgurl = findall(
                        "(?<=imgurl=).*(?=&imgrefurl)",
                        image.findAll("img")[1].parent.parent["href"],
                    )[0]

                return imgurl
            except Exception:
                raise

        # endregion

        # region embed creation functions
        # embed creation for image embeds
        def image_embed(image) -> Embed:
            try:
                # creates and formats the embed
                result_embed = Embed(
                    title=f"Search results for: {self.search_query[:233]}"
                    f'{"..." if len(self.search_query) > 233 else ""}'
                )

                # sets the discord embed to the image
                result_embed.set_image(url=image_url_parser(image))
                result_embed.url = url
            except:
                result_embed.description = "Image failed to load"
            finally:
                return result_embed

        # embed creation for text embeds
        def text_embed(result) -> Embed:
            # creates and formats the embed
            result_embed = Embed(
                title=f'Search results for: {self.search_query[:233]}{"..." if len(self.search_query) > 233 else ""}'
            )

            # google results are separated by divs
            # extracts all meaningful text in the search result by div
            result_find = result.findAll("div")
            divs = tuple(d for d in result_find if not d.find("div"))
            lines = tuple(
                " ".join(
                    [
                        string if string != "View all" else ""
                        for string in div.stripped_strings
                    ]
                )
                for div in divs
            )
            printstring = "\n".join(lines)

            # discord prevents embeds longer than 2048 chars
            # truncates adds ellipses to strings longer than 2048 chars
            if len(printstring) > 2048:
                printstring = printstring[:2045] + "..."

            # sets embed description to string
            result_embed.description = sub("\n\n+", "\n\n", printstring)

            # searches for link in div
            find_link = result.findAll("a", href_="")
            link_list = tuple(a for a in find_link if not a.find("img"))
            if len(link_list) != 0:
                try:
                    # parses link from html
                    link = link_unicode_parse(
                        findall(r"(?<=url\?q=).*(?=&sa)", link_list[0]["href"])[0]
                    )

                    # adds link to embed
                    result_embed.add_field(name="Relevant Link", value=link)
                    print(" link: " + link)
                except:
                    print("adding link failed")

            # tries to add an image to the embed
            image = result.find("img")
            try:
                result_embed.set_image(url=image_url_parser(image))
            except:
                pass
            result_embed.url = url
            return result_embed

        # endregion

        try:
            # checks if image is in search query
            if bool(search("image", self.search_query.lower())):
                has_found_image = True
            else:
                has_found_image = False

            # gets uule string based on user settings
            if self.userSettings[self.ctx.author.id]["locale"] is not None:
                uule_parse = uule(self.userSettings[self.ctx.author.id]["locale"])
            else:
                # default uule is Google HQ
                uule_parse = "w+CAIQICI5TW91bnRhaW4gVmlldyxTYW50YSBDbGFyYSBDb3VudHksQ2FsaWZvcm5pYSxVbml0ZWQgU3RhdGVz"

            # creates google search url
            # format: https://google.com/search?pws=0&q=[query]&uule=[uule string]&num=[number of results]&safe=[safesearch status]
            url = "".join(
                [
                    "https://google.com/search?pws=0&q=",
                    self.search_query.replace(" ", "+"),
                    f'{"+-stock+-pinterest" if has_found_image else ""}',
                    f"&uule={uule_parse}&num=5"
                    f"{'&safe=active' if self.serverSettings[hex(self.ctx.guild.id)]['safesearch'] and not self.ctx.channel.nsfw else ''}",
                ]
            )

            # gets the webscraped html of the google search
            response = get(url)
            soup, index = BeautifulSoup(response.text, features="lxml"), 3

            # Debug HTML output
            # with open('test.html', 'w', encoding='utf-8-sig') as file:
            #    file.write(soup.prettify())

            # if the search returns results
            if soup.find("div", {"id": "main"}) is not None:
                Log.append_to_log(self.ctx, f"{self.ctx.command} results", url)
                google_snippet_results = soup.find("div", {"id": "main"}).contents

                # region html processing
                # html div cleanup
                google_snippet_results = [
                    google_snippet_results[resultNumber]
                    for resultNumber in range(3, len(google_snippet_results) - 2)
                ]

                # bad divs to discard
                wrong_first_results = {
                    "Did you mean: ",
                    "Showing results for ",
                    "Tip: ",
                    "See results about",
                    "Including results for ",
                    "Related searches",
                    "Top stories",
                    "People also ask",
                    "Next >",
                }
                # bad div filtering
                google_snippet_results = {
                    result
                    for result in google_snippet_results
                    if not any(
                        badResult in result.strings for badResult in wrong_first_results
                    )
                    or result.strings == ""
                }
                # endregion

                # checks if user searched specifically for images
                images, embeds = None, None
                if has_found_image:
                    # searches for the "images for" search result div
                    for results in google_snippet_results:
                        if "Images" in results.strings:
                            images = results.findAll("img", recursive=True)
                            embeds = list(map(image_embed, images))
                            if len(embeds) > 0:
                                del embeds[-1]
                            break

                if embeds is None:
                    embeds = list(map(text_embed, google_snippet_results))

                print(
                    self.ctx.author.name + " searched for: " + self.search_query[:233]
                )

                # adds the page numbering footer to the embeds
                for index, item in enumerate(embeds):
                    item.set_footer(
                        text=f"Page {index+1}/{len(embeds)}\nRequested by: {str(self.ctx.author)}"
                    )

                # sets the reactions for the search result
                if len(embeds) > 1:
                    await gather(
                        self.message.add_reaction("🗑️"),
                        self.message.add_reaction("◀️"),
                        self.message.add_reaction("▶️"),
                    )
                else:
                    await self.message.add_reaction("🗑️")

                # multipage result display
                do_exit, cur_page = False, 0
                while not do_exit:
                    try:
                        await self.message.edit(
                            content=None, embed=embeds[cur_page % len(embeds)]
                        )

                        reaction, user = await self.bot.wait_for(
                            "reaction_add",
                            check=lambda reaction_, user_: all(
                                [
                                    user_ == self.ctx.author,
                                    str(reaction_.emoji) in ["◀️", "▶️", "🗑️"],
                                    reaction_.message == self.message,
                                ]
                            ),
                            timeout=60,
                        )
                        await self.message.remove_reaction(reaction, user)

                        if str(reaction.emoji) == "🗑️":
                            await self.message.delete()
                            do_exit = True
                        elif str(reaction.emoji) == "◀️":
                            cur_page -= 1
                        elif str(reaction.emoji) == "▶️":
                            cur_page += 1

                    except TimeoutError:
                        await self.message.clear_reactions()
                        raise

            else:
                embed = Embed(
                    title=f'Search results for: {self.search_query[:233]}{"..." if len(self.search_query) > 233 else ""}',
                    description="No results found. Maybe try another search term.",
                )

                embed.set_footer(text=f"Requested by {self.ctx.author}")
                await self.message.edit(content=None, embed=embed)
                try:
                    await self.message.add_reaction("🗑️")
                    reaction, user = await self.bot.wait_for(
                        "reaction_add",
                        check=lambda reaction_, user_: all(
                            [
                                user_ == self.ctx.author,
                                reaction_.message == self.message,
                                str(reaction_.emoji) == "🗑️",
                            ]
                        ),
                        timeout=60,
                    )
                    if str(reaction.emoji) == "🗑️":
                        await self.message.delete()

                except TimeoutError:
                    raise

        except TimeoutError:
            raise

        except Exception as e:
            await self.message.delete()
            await error_handler(self.bot, self.ctx, e, self.search_query)
        finally:
            return

    async def translate(self) -> None:
        try:
            # translate string processing
            query = self.search_query.lower().split(" ")

            if len(query) > 1:
                # processes keywords in query for language options
                del query[0]
                if "to" in query:
                    dest_language = languages.get(
                        name=query[query.index("to") + 1].lower().capitalize()
                    ).alpha2
                    del query[query.index("to") + 1]
                    del query[query.index("to")]
                else:
                    dest_language = "en"

                if "from" in query:
                    src_language = languages.get(
                        name=query[query.index("from") + 1].lower().capitalize()
                    ).alpha2
                    del query[query.index("from") + 1]
                    del query[query.index("from")]
                else:
                    src_language = None

                # creates query
                query = " ".join(query)

                # queries Google Translate for translations
                translator = Translator(
                    to_lang=dest_language,
                    from_lang=f"{src_language if src_language is not None else detect(query)[0]}",
                )
                result = translator.translate(query)

                # creates and sends embed
                if isinstance(result, list):
                    result = "\n".join(result)
                embed = Embed(
                    title=f"{languages.get(alpha2=translator.from_lang).name}"
                    + f" to {languages.get(alpha2=translator.to_lang).name} Translation",
                    description=result + "\n\nReact with 🔍 to search Google",
                )
                embed.set_footer(text=f"Requested by {self.ctx.author}")
                await self.message.edit(content=None, embed=embed)

                # waits for user reaction options
                await self.message.add_reaction("🗑️")
                await self.message.add_reaction("🔍")
                reaction, _ = await self.bot.wait_for(
                    "reaction_add",
                    check=lambda reaction_, user_: all(
                        [
                            user_ == self.ctx.author,
                            str(reaction_.emoji) in ["🔍", "🗑️"],
                        ]
                    ),
                    timeout=60,
                )

                if str(reaction.emoji) == "🗑️":
                    await self.message.delete()
                    return

                # deletes translation and gives the user the Google results
                elif str(reaction.emoji) == "🔍":
                    await self.message.clear_reactions()
                    await self.message.edit(
                        content=f"{get_loading_message()} <a:loading:829119343580545074>",
                        embed=None,
                    )
                    await self.search()
                    pass

            else:
                await self.message.edit(
                    content=f"{get_loading_message()} <a:loading:829119343580545074>",
                    embed=None,
                )
                await self.search()

        except KeyError:
            await self.message.clear_reactions()
            await self.message.edit(
                content=f"{get_loading_message()} <a:loading:829119343580545074>",
                embed=None,
            )
            await self.search()

        except TimeoutError:
            raise

        except Exception as e:
            await self.message.delete()
            await error_handler(self.bot, self.ctx, e, self.search_query)
            await self.message.edit(
                content=f"{get_loading_message()} <a:loading:829119343580545074>",
                embed=None,
            )
            await self.search()

        finally:
            return

    async def define(self) -> None:
        try:
            # creates the embed for each definition result
            def definition_embed(word, response) -> List[Embed]:
                embeds = []
                for definition in word["definitions"]:
                    embeds.append(
                        Embed(
                            title=f'Definition of: {response["word"]}',
                            description="\n".join(
                                [
                                    f'{response["word"]}',
                                    f'`{response["phonetics"][0]["text"]}`',
                                    "\n",
                                    f'{word["partOfSpeech"]}',
                                    f'{definition["definition"]}',
                                    "\n",
                                ]
                            ),
                        )
                    )
                    embeds[-1].add_field(
                        name="Synonyms",
                        value=", ".join(definition["synonyms"])
                        if "synonyms" in definition.keys()
                        else "None",
                    )
                    embeds[-1].add_field(
                        name="Example",
                        value=definition["example"]
                        if "example" in definition.keys()
                        else "None",
                    )
                    embeds[-1].add_field(
                        name="Pronounciation Guide",
                        value=response["phonetics"][0]["audio"],
                        inline=False,
                    )
                    embeds[
                        -1
                    ].url = f'https://www.merriam-webster.com/dictionary/{response["word"]}'
                return embeds

            # definition string processing
            query = self.search_query.lower().split(" ")

            if len(query) > 1:
                # queries dictionary API
                response = get(
                    f'https://api.dictionaryapi.dev/api/v2/entries/en_US/{" ".join(query[1:])}'
                )
                response = response.json()[0]

                # creates embed
                embeds = [
                    item
                    for sublist in [
                        definition_embed(word, response)
                        for word in response["meanings"]
                    ]
                    for item in sublist
                ]
                for index, item in enumerate(embeds):
                    item.set_footer(
                        text=f"Page {index+1}/{len(embeds)}\n"
                        f"React with 🔍 to search Google\n"
                        f"Requested by: {str(self.ctx.author)}"
                    )

                # user react option system
                cur_page = 0
                await self.message.add_reaction("🗑️")
                await self.message.add_reaction("🔍")
                if len(embeds) > 1:
                    await self.message.add_reaction("◀️")
                    await self.message.add_reaction("▶️")

                # multipage definition display
                while 1:
                    await self.message.edit(
                        content=None, embed=embeds[cur_page % len(embeds)]
                    )
                    reaction, user = await self.bot.wait_for(
                        "reaction_add",
                        check=lambda reaction_, user_: all(
                            [
                                user_ == self.ctx.author,
                                str(reaction_.emoji) in ["◀️", "▶️", "🗑️", "🔍"],
                                reaction_.message == self.message,
                            ]
                        ),
                        timeout=60,
                    )
                    await self.message.remove_reaction(reaction, user)

                    if str(reaction.emoji) == "🗑️":
                        await self.message.delete()
                        return
                    elif str(reaction.emoji) == "◀️":
                        cur_page -= 1
                    elif str(reaction.emoji) == "▶️":
                        cur_page += 1

                    # gives the user Google results
                    elif str(reaction.emoji) == "🔍":
                        await self.message.clear_reactions()
                        await self.message.edit(
                            content=f"{get_loading_message()} <a:loading:829119343580545074>",
                            embed=None,
                        )
                        await self.search()
                        break

            else:
                await self.message.edit(
                    content=f"{get_loading_message()} <a:loading:829119343580545074>",
                    embed=None,
                )
                await self.search()

        except TimeoutError:
            raise

        except Exception as e:
            await self.message.delete()
            await error_handler(self.bot, self.ctx, e, self.search_query)
            await self.message.edit(
                content=f"{get_loading_message()} <a:loading:829119343580545074>",
                embed=None,
            )
            await self.search()

        finally:
            return
