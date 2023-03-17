import json
import numpy as np
from operator import getitem
import os

def get_all_players(hands):
    playersList = set()
    for hand in hands:
        for player in hand['players']:
            if player['name'] not in playersList:
                playersList.add(player['name'])

    return playersList

def write_stats(file, finalDict, statsList, list=None, strip=True):
    if strip and list:
        for i in range(len(list)):
            list[i] = list[i].replace(' ', '').lower()

    with open(file, 'w', encoding="utf-8") as f:
        for (key, value) in finalDict:
            if (not list) or (not list or key in list):
                d = {k: value[k] for k in value if k in statsList}
                f.write(f"{key} | {str(d)}\n")
    
def div(n, d):
    return (n / d) if d != 0 else 0

def merge(start, end, strip=True):
    for (key, value) in start:
        if strip:
            key = key.replace(' ', '').replace('.', '').lower()

        if key not in end:
            end[key] = value
            end[key]['count'] = 1
        else:
            for k in value:
                end[key][k] += value[k]
            end[key]['count'] += 1

def normal(d):
    finalDict = {}
    for (key, value) in d.items():
        newDict = {}
        for (key1, value1) in value.items():
                newDict[key1] = np.round(value1 / \
                (value['count'] if key1 not in ['Hands', 'count'] else 1), 2)
        finalDict[key] = newDict
    return finalDict

def read_hand(hand, masterDict):
    def add(numRaise, playerName):
        #print(numRaise)
        if numRaise == 0:
            masterDict[playerName]['totalRFI'] += 1
        elif numRaise == 1:
            masterDict[playerName]['total3Bet'] += 1
        elif numRaise == 2:
            masterDict[playerName]['total4Bet'] += 1

    players = hand['players']
    playerDict = {}
    for player in players:
        playerName = player['seat']
        playerDict[playerName] = (player['name'], player['stack'])
        masterDict[player['name']]['numHands'] += 1

    events = hand['events']
    for event in events:
        if event['payload']['type'] == 2:
            bbSeat = event['payload']['seat']
            bbName = playerDict[bbSeat][0]
            break

    profitDict = dict()
    currStreet = 0 # 0 = preflop, 1 = flop, 2 = turn, 3 = river
    streetProfit = dict()
    numRaise = 0 # 0 = rfi, 1 = 3bet, 2 = 4bet

    # Squeezing
    numCallers = -1
    initialRaiser = None
    for event in events:
        payload = event['payload']
        eventType = payload['type']
        if eventType >= 12 and eventType != 16: # ignore
            continue

        if eventType == 9: # next card
            currStreet += 1
            for playerName in streetProfit:
                profitDict[playerName] = profitDict.get(playerName, 0) - streetProfit[playerName]
                streetProfit[playerName] = 0
            continue

        (playerName, playerStack) = playerDict[payload['seat']]

        if eventType == 10 or eventType == 16:
            profitDict[playerName] = profitDict.get(playerName, 0) + payload['value']
        elif 'value' in payload:
            streetProfit[playerName] = payload['value']

        if eventType == 10: # hand finished
            for player in streetProfit:
                profitDict[player] = profitDict.get(player, 0) - streetProfit[player]
                streetProfit[player] = 0
            continue

        if currStreet == 0:
            if eventType == 11:
                masterDict[playerName]['numFold'] += 1
                add(numRaise, playerName)
                
                if numRaise == 2:
                    if initialRaiser == playerName:
                        masterDict[playerName]['vs3Bet']['3BetFold'] += 1
            elif eventType == 7:
                # call
                numCallers += 1
                add(numRaise, playerName)

                if numRaise == 2:
                    if initialRaiser == playerName:
                        masterDict[playerName]['vs3Bet']['3BetCall'] += 1
            elif eventType == 8:
                # raise
                add(numRaise, playerName)
                if numCallers >= 1:
                    masterDict[playerName]['numSqz'] += 1
                    masterDict[playerName]['totalSqz'] += numCallers

                if numRaise == 0:
                    masterDict[playerName]['numRFI'] += 1
                    numRaise += 1
                    initialRaiser = playerName
                elif numRaise == 1:
                    masterDict[playerName]['num3Bet'] += 1
                    numRaise += 1
                elif numRaise == 2:
                    masterDict[playerName]['num4Bet'] += 1
                    if initialRaiser == playerName:
                        masterDict[playerName]['vs3Bet']['4Bet'] += 1
                    numRaise += 1
                # potentially add 5Bet+
                
                numCallers = 0
            elif eventType == 0:
                if payload['seat'] == bbSeat:
                    masterDict[playerName]['numCheckBB'] += 1

    #print(hand['number'], bbName, profitDict)

    masterDict[bbName]['bbProfit'] += (profitDict[bbName] / hand["bigBlind"])
    masterDict[bbName]['numBB'] += 1

    for player in profitDict:
        masterDict[player]['profit'] += profitDict[player]
    #print(hand['number'], bbName, profitDict[bbName] / hand["bigBlind"])

#####################

essential_info_stats = ['Hands', 'PFR', 'RFI', 'VPIP', '3Bet', '4Bet', 'F3', 'count']
extra_info_stats = ['Hands', 'Sqz', 'SqzAvg', 'bbAvg', 'profit', 'avgProfit']
def read_single_game(file, write=True, sortedKey='VPIP', short=-1, minHands=1):
    # short = 0 -> 6+, short = 1 -> 2-6, short = 2 -> hu
    with open(file, 'r', encoding="utf-8") as f:
        data = json.loads(f.read())

    hands = data['hands']

    masterDict = {player: 
        {
            'numHands': 0, 
            'numRFI': 0,
            'totalRFI': 0,
            'numFold': 0,
            'vs3Bet': {
                '3BetCall': 0,
                '4Bet': 0,
                '3BetFold': 0,
            },
            'num3Bet': 0,
            'total3Bet': 0,
            'num4Bet': 0,
            'total4Bet': 0,
            'numSqz': 0,
            'totalSqz': 0,
            'bbProfit': 0,
            'numBB': 0,
            'numCheckBB': 0,
            'profit': 0
        }
        for player in get_all_players(hands)
    }

    for hand in hands:
        if (short == 2 and len(hand['players']) == 2) or \
            (short == 1 and 3 <= len(hand['players']) <= 6) or \
            (short == 0 and 6 < len(hand['players'])) or \
                (short == -1):
                read_hand(hand, masterDict)

    finalDict = dict()
    for player in masterDict:
        d = masterDict[player]
        if d['numHands'] < minHands:
            continue
        
        total3Bet = masterDict[player]['vs3Bet']['3BetFold'] + \
                    masterDict[player]['vs3Bet']['3BetCall'] + \
                    masterDict[player]['vs3Bet']['4Bet']

        """
        print(player, masterDict[player]['vs3Bet']['3BetFold'],
              masterDict[player]['vs3Bet']['3BetCall'],
              masterDict[player]['vs3Bet']['4Bet'])
        """
        
        finalDict[player] = {
            'Hands': d['numHands'],
            'RFI': div(d['numRFI'], d['totalRFI']) * 100,
            'PFR': div(d['numRFI'] + d['num3Bet'], d['numHands']) * 100,
            'VPIP': (d['numHands'] - d['numFold'] - d['numCheckBB']) / d['numHands'] * 100,
            '3Bet': div(d['num3Bet'], d['total3Bet']) * 100,
            '4Bet': div(d['num4Bet'], d['total4Bet']) * 100,
            'F3': div(d['vs3Bet']['3BetFold'], total3Bet) * 100,
            'Sqz': d['numSqz'] / d['numHands'] * 100,
            'SqzAvg': div(d['totalSqz'], d['numSqz']),
            'bbAvg': div(d['bbProfit'], d['numBB']),
            'profit': d['profit'],
            'avgProfit': d['profit'] / d['numHands']
        }
        
        for stat in finalDict[player]:
            finalDict[player][stat] = np.round(finalDict[player][stat], 2)

    finalDict = sorted(finalDict.items(), key=lambda x:getitem(x[1], sortedKey), reverse=True)
    
    if write:
        write_stats('stats/current/essential_info.txt', finalDict, essential_info_stats)
        write_stats('stats/current/extra_info.txt', finalDict, extra_info_stats)
    
    return finalDict

def classify_players(file, d):
    g = dict()
    with open(file, 'w', encoding='utf-8') as f:
        for (key, value) in d:
            vpip = value['VPIP']
            pfr = value['PFR']
            label = ""
            if (pfr <= 5):
                label = "rock"
            elif (vpip >= 40):
                if (vpip <= pfr*4):
                    label = "big whale"
                else:
                    label = "aggro fish"
            elif (vpip >= 30):
                if (vpip <= pfr*2):
                    label = "small whale"
                else:
                    label = "fish"
            elif (vpip >= 22):
                if (abs(vpip - pfr) <= 5):
                    label = "good loose reg"
                elif (abs(vpip - pfr) <= 10):
                    label = "decent loose reg"
                else:
                    label = "loose rock"
            elif (vpip >= 15):
                if (abs(vpip - pfr) <= 3):
                    label = "good tight reg"
                elif (abs(vpip - pfr) <= 6):
                    label = "decent tight reg"
                else:
                    label = "tight rock"
            else:
                label = "nit"
            
            #f.write(f"{key} | {label}\n")
            if label in g:
                g[label].add(key)
            else:
                g[label] = set([key])
        
        for key in g:
            f.write(f"{key}: {str(g[key])}\n")

def read_multiple_games(dir, sortedKey='VPIP', list=None, strip=True, minHands=1):
    shortDict = {}
    deepDict = {}
    huDict = {}
    for file in os.listdir(dir):
        f = os.path.join(dir, file)
        gameDeepDict = read_single_game(f, write=False, short=0, minHands=minHands)
        gameShortDict = read_single_game(f, write=False, short=1, minHands=minHands)
        gameHUDict = read_single_game(f, write=False, short=2, minHands=minHands)
        merge(gameShortDict, shortDict, strip=strip)
        merge(gameDeepDict, deepDict, strip=strip)
        merge(gameHUDict, huDict, strip=strip)

    shortDict = normal(shortDict)
    shortDict = sorted(shortDict.items(), key=lambda x:getitem(x[1], sortedKey), reverse=True)
    write_stats('stats/short/essential_info.txt', shortDict, essential_info_stats, list, strip)
    write_stats('stats/short/extra_info.txt', shortDict, extra_info_stats, list, strip)

    deepDict = normal(deepDict)
    deepDict = sorted(deepDict.items(), key=lambda x:getitem(x[1], sortedKey), reverse=True)
    write_stats('stats/deep/essential_info.txt', deepDict, essential_info_stats, list, strip)
    write_stats('stats/deep/extra_info.txt', deepDict, extra_info_stats, list, strip)
    classify_players('stats/deep/class.txt', deepDict)

    huDict = normal(huDict)
    huDict = sorted(huDict.items(), key=lambda x:getitem(x[1], sortedKey), reverse=True)
    write_stats('stats/hu/essential_info.txt', huDict, essential_info_stats, list, strip)
    write_stats('stats/hu/extra_info.txt', huDict, extra_info_stats, list, strip)

#read_single_game('games/mason.json', write=True)
read_multiple_games('games', sortedKey='VPIP', list=None, strip=True, minHands=100)

