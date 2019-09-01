"""
Módulo para comandos do bot. Neste arquivo deverão conter apenas funções de
chamada dos comandos que o bot responde. Demais algoritmos, mesmo contendo
o processamento destas funções devem estar em um outro módulo dedicado e
importá-lo neste escopo, deixando este módulo o mais limpo possível e
facilitando a identificação e manutenção dos comandos.
"""
from random import choice
import discord
from discord.ext import commands
from discord.utils import get
from settings import (LISA_URL, RANKED_SPREADSHEET_ID, SCORE_INDEX, SD_NAME_INDEX, ADMIN_CHANNEL, COLOR_INDEX, ELO_IMG_INDEX)
from util.general_tools import (get_similar_pokemon, get_trainer_rank,
                                get_ranked_spreadsheet, get_form_spreadsheet, compare_insensitive, get_embed_output,
                                get_table_output, get_trainer_rank_row)
from util.get_api_data import (dex_information, get_pokemon_data, 
                               get_item_data, item_information,
                               get_ability_data, ability_information)
from util.showdown_battle import load_battle_replay
from util.elos import (Elos, get_elo, validate_elo_battle, ELOS_MAP)
import requests
import json
import random
from datetime import datetime


client = commands.Bot(command_prefix='/')


@client.event
async def on_ready():
    """
    Imprime uma mensagem no console informando que o bot, a princípio executou
    corretamente.
    """
    print("The bot is ready!")


@client.event
async def on_member_join(member):
    # TODO I think this should be removed, since is is unused, or, adapt to
    # send an welcome text on member join ...
    # maybe thats the real reason for this piece of code to exist ¯\(°_o)/¯
    print('{} entrou no rolê!'.format(member))


@client.event
async def on_member_remove(member):
    # TODO I think this should be removed, since is is unused, or, adapt to
    # send an welcome text on member join ...
    # maybe thats the real reason for this piece of code to exist ¯\(°_o)/¯
    print('{} saiu do rolê!'.format(member))


@client.command()
async def ping(ctx):
    """
    Verifica se o bot está executando. Responde com "pong" caso positivo.
    """
    await ctx.send('pong')


@client.command()
async def dex(ctx, pokemon):
    """
    Responde informações sobre um pokemon.
    """
    poke = get_pokemon_data(pokemon.lower())
    response = dex_information(poke)
    if not response:
        response = 'Pokémon não registrado na PokeDex.\n'
        response += 'Talvez você queira dizer: {}'.format(
            get_similar_pokemon(pokemon)
        )

    await ctx.send(response)


@client.command()
async def item(ctx, item):
    """
    Responde informações sobre um item.
    """
    data = get_item_data(item.lower())
    response = item_information(data)
    await ctx.send(response)


@client.command()
async def ability(ctx, ability):
    """
    Responde informações sobre uma habilidade
    """
    data = get_ability_data(ability.lower())
    response = ability_information(data)
    await ctx.send(response)


@client.command()
async def quote(ctx, *phrase):
    """
    Salva uma mensagem como quote para ser eternamente lembrado
    """
    if phrase:
        quoted = ' '.join(word for word in phrase)

        # TODO build the query in another dedicated module and import here
        part_1 = "{\"query\":\"mutation{\\n  createAbpQuote(input:{\\n    quote: \\\" " 
        part_2 = "\\\"\\n  }){\\n    response\\n  }\\n}\"}"
        headers = {
            'content-type': "application/json"
            }
        payload = part_1 + quoted + part_2
        response = requests.request("POST", LISA_URL, data=payload, headers=headers)
        response = json.loads(response.text)
        response = response['data']['createAbpQuote'].get('response')

    else:
        response = "Insira alguma pérola!"

    await ctx.send(response)


@client.command()
async def random_quote(ctx):
    """
    Retorna um quote aleatório
    """
    # TODO build the query in another dedicated module and import here
    payload = "{\"query\":\"query{\\n  abpQuotes\\n}\"}"
    headers = {
        'content-type': "application/json"
        }

    # TODO Exchange requests for gql module
    response = requests.request("POST", LISA_URL, data=payload, headers=headers)
    response = json.loads(response.text)
    quotes = response['data'].get('abpQuotes')

    await ctx.send(choice(quotes))


@client.command()
async def random_pokemon(ctx):
    """
    Responde com um pokémon aleatório
    """
    with open('files/pokes.txt', 'r') as f:
        pokes = f.readlines()

    i_choose_you = choice(pokes).split('\n')[0]
    poke = get_pokemon_data(i_choose_you.lower())
    response = dex_information(poke)
    await ctx.send(response)


@client.command()
async def top_ranked(ctx, *args):
    """
    Informa os 20 primeiros colocados da Ranked ABP.
    """
    data = get_ranked_spreadsheet()
    table = get_initial_ranked_table()
    
    view_types = [
        [ "list", "lista", "elos" ],
        [ "table", "tabela" ]
    ]
    is_list = len(args) > 0 and args[0].strip().lower() in view_types[0]

    for i, trainer in enumerate(data[:20], start=1):
        trainer = get_trainer_rank_row(trainer, i)
        table.append(trainer)

    if is_list:
        descript = "**__Top Players__**"
        output = get_embed_output(table, client)
        await ctx.send(descript, embed=output)
    else:
        output = get_table_output(table)
        await ctx.send(output)


@client.command()
async def ranked_trainer(ctx, *trainer_nickname):
    """
    Busca o score de um trainer na ranked pelo nick do caboclo.
    """
    if not trainer_nickname:
        await ctx.send('Forneça um nick\nUso: `/ranked_trainer <nickname>`')
        return
    
    trainer_nickname = ' '.join(word for word in trainer_nickname)
    trainer = find_trainer(trainer_nickname)

    if not trainer:
        await ctx.send('Treinador não encontrado')
        return

    # lookup for the trainer elo data
    nick = "**__"+ trainer[1] +"__**"
    elo_rank = get_trainer_rank(trainer[SCORE_INDEX])
    elo = elo_rank.lower().replace("á", "a")
    elo_data = [item for item in ELOS_MAP if item[0] == elo][0]

    # setup embed data
    embed = discord.Embed(color=elo_data[COLOR_INDEX], type="rich")
    embed.set_thumbnail(url=elo_data[ELO_IMG_INDEX])
    
    embed.add_field(name="Pos", value=trainer[6], inline=True)
    embed.add_field(name="Elo", value=elo_rank, inline=True)
    embed.add_field(name="Wins", value=trainer[2], inline=True)
    embed.add_field(name="Losses", value=trainer[3], inline=True)
    embed.add_field(name="Battles", value=trainer[5], inline=True)
    embed.add_field(name="Points", value=trainer[4], inline=True)
    
    await ctx.send(nick, embed=embed)


@client.command()
async def ranked_elo(ctx, *elo_arg):
    """
    Retorna todos os treinadores que estão no Rank Elo solicitado.
    """
    if not elo_arg:
        await ctx.send('Forneça um Rank Elo\nUso: `/ranked_elo <elo>`')
        return

    elo = ' '.join(word for word in elo_arg)
    data = get_ranked_spreadsheet()
    table = get_initial_ranked_table()
    
    for i, trainer in enumerate(data, start=1):
        rank =  get_trainer_rank(trainer[SCORE_INDEX])
        isTargetElo = compare_insensitive(rank, elo)
        if isTargetElo:
            trainer = get_trainer_rank_row(trainer, i)       
            table.append(trainer)
    
    # only table header
    if len(table) == 1:
        await ctx.send('Treinadores não encontrados para o Elo: ' + elo)
        return

    # when too big table, shows just the first 20
    if len(table) > 20:
        table = table[:21]
        await ctx.send('Top 20 treinadores do Elo: ' + elo)
    
    output = get_table_output(table)
    await ctx.send(output)


@client.command()
async def ranked_validate(ctx):
    """
    Valida as entradas pendentes do formulário de registro de batalhas
    """
    if ctx.message.channel.name != ADMIN_CHANNEL:
        return

    data = get_form_spreadsheet()
    ranked_data = get_ranked_spreadsheet()
    errors = [
        [ "Ln.", "Error" ]
    ]
    ok = [ 'http://i.imgur.com/dTysUHw.jpg', 'https://media.tenor.com/images/4439cf6a16b577d81f6e06b9ba2fd278/tenor.gif', 'https://i.kym-cdn.com/photos/images/original/001/092/497/a30.jpg', 'https://i.kym-cdn.com/entries/icons/facebook/000/012/542/thumb-up-terminator_pablo_M_R.jpg', 'https://media.giphy.com/media/111ebonMs90YLu/giphy.gif' ]
    
    for i, row in enumerate(data, start=2):
        # validate trainers
        trainers_result = ""
        winner_data = find_trainer(row[2], ranked_data)
        loser_data  = find_trainer(row[3], ranked_data)
        if winner_data == None: trainers_result += "Winner not found; "
        if loser_data  == None: trainers_result += "Loser not found; "
        if trainers_result != "":
            errors.append([i, trainers_result])
            continue

        # validate elos
        winner_elo  = get_elo(get_trainer_rank(winner_data[SCORE_INDEX]))
        loser_elo   = get_elo(get_trainer_rank(loser_data[SCORE_INDEX]))
        valid_elos  = validate_elo_battle(winner_elo, loser_elo)
        if not valid_elos:
            errors.append([i, "Invalid elos matchup ({} vs {})".format(winner_elo.name, loser_elo.name)])
            continue
        
        # validate showdown replay
        result = load_battle_replay(row[4]) # 4 is the replay
        if not result.success:
            errors.append([i, "Não foi possivel carregar o replay" ])
            continue
        
        # validate replay metadata
        battle_result = result.battle.validate(row[2], row[3], datetime.strptime(row[0], "%d/%m/%Y %H:%M:%S"))
        if not battle_result.success:
            errors.append([i, battle_result.error])

    # only table header
    if len(errors) == 1:
        await ctx.send('All good! 👍 ' + ok[random.randint(0, len(ok)-1)])
        return

    # when too big errors table, split into smaller data
    chunks = [errors[x:x+10] for x in range(0, len(errors), 10)]
    for err in chunks:
        output = get_table_output(err)
        await ctx.send(output)


# TODO move this to an util or tools dedicated module
def get_initial_ranked_table():
    """
    Retorna uma lista contendo uma lista com as colunas a serem exibidas
    no placar da Ranked.

    params : None :
    return : <list> :
    """
    return [
        [ 'Pos', 'Nick', 'Wins', 'Bts', 'Pts', 'Rank' ],
    ]


# TODO move this to an util or tools dedicated module
def find_trainer(trainer_nickname, data = None):
    """
    Procura por um treinador específico na tabela de treinadores da ranked.

    param : trainer_nickname : <str>
    param : data : <list> : param data default value : None
                    TODO <- corrija-me se eu estiver errado Thiago Menezes
    return : <list>
    """
    data = data if data != None else get_ranked_spreadsheet()
    pos = 0
    for trainer in data:
        pos += 1
        trainer_found = compare_insensitive(trainer[SD_NAME_INDEX], trainer_nickname)
        if trainer_found:
            trainer.append(pos)
            return trainer

    return None
