# -*- coding: utf-8 -*-
from __future__ import absolute_import

import hashlib

from collections import namedtuple

from sc2reader import utils
from sc2reader.constants import *

Location = namedtuple('Location',('x','y'))
MapData = namedtuple('MapData',['gateway','map_hash'])
ColorData = namedtuple('ColorData',['a','r','g','b'])
BnetData = namedtuple('BnetData',['gateway','unknown2','subregion','uid'])

class Team(object):
    """
    The team object primarily a container object for organizing :class:`Player`
    objects with some metadata. As such, it implements iterable and can be
    looped over like a list.

    :param interger number: The team number as recorded in the replay
    """

    #: A unique hash identifying the team of players
    hash = str()

    #: The team number as recorded in the replay
    number = int()

    #: A list of the :class:`Player` objects on the team
    players = list()

    #: The result of the game for this team.
    #: One of "Win", "Loss", or "Unknown"
    result = str()

    def __init__(self, number):
        self.number = number
        self.players = list()
        self.result = "Unknown"

    def __iter__(self):
        return self.players.__iter__()

    @property
    def lineup(self):
        """
        A string representation of the team play races like PP or TPZZ. Random
        pick races are not reflected in this string
        """
        return ''.join(sorted(p.play_race[0].upper() for p in self.players))

    @property
    def hash(self):
        raw_hash = ','.join(sorted(p.url for p in self.players))
        return hashlib.sha256(raw_hash).hexdigest()

    def __str__(self):
        return "Team {0}".format(self.number)


class Attribute(object):

    def __init__(self, header, attr_id, player, value):
        self.header = header
        self.id = attr_id
        self.player = player

        if self.id not in LOBBY_PROPERTIES:
            raise ValueError("Unknown attribute id: "+self.id)
        else:
            self.name, lookup = LOBBY_PROPERTIES[self.id]
            self.value = lookup[value.strip("\x00 ")[::-1]]

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "[%s] %s: %s" % (self.player, self.name, self.value)


class Entity(object):
    """
    :param integer sid: The entity's unique slot id.
    :param dict slot_data: The slot data associated with this entity
    """
    def __init__(self, sid, slot_data):
        #: The entity's unique in-game slot id
        self.sid = int(sid)

        #: The entity's replay.initData slot data
        self.slot_data = slot_data

        #: The player's handicap as set prior to game start, ranges from 50-100
        self.handicap = slot_data['handicap']

        #: The entity's team number. None for observers
        self.team_id = slot_data['team_id']+1

        #: A flag indicating if the person is a human or computer
        #: Really just a shortcut for isinstance(entity, User)
        self.is_human = slot_data['control'] == 2

        #: A flag indicating the entity's observer status.
        #: Really just a shortcut for isinstance(entity, Observer).
        self.is_observer = slot_data['observe'] != 0

        #: A flag marking this entity as a referee (can talk to players)
        self.is_referee = slot_data['observe'] == 2

        #: The unique Battle.net account identifier in the form of
        #: <region_id>-S2-<subregion>-<toon_id>
        self.toon_handle = slot_data['toon_handle']

        toon_handle = self.toon_handle or "0-S2-0-0"
        parts = toon_handle.split("-")

        #: The Battle.net region the entity is registered to
        self.region = GATEWAY_LOOKUP[int(parts[0])]

        #: Deprecated, see Entity.region
        self.gateway = self.region

        #: The Battle.net subregion the entity is registered to
        self.subregion = int(parts[2])

        #: The Battle.net acount identifier. Used to construct the
        #: bnet profile url. This value can be zero for games
        #: played offline when a user was not logged in to battle.net.
        self.toon_id = int(parts[3])

        #: A list of :class:`Event` objects representing all the game events
        #: generated by the person over the course of the game
        self.events = list()

        #: A list of :class:`~sc2reader.events.message.ChatEvent` objects representing all of the chat
        #: messages the person sent during the game
        self.messages = list()

    def format(self, format_string):
        return format_string.format(**self.__dict__)


class Player(object):
    """
    :param integer pid: The player's unique player id.
    :param dict detail_data: The detail data associated with this player
    :param dict attribute_data: The attribute data associated with this player
    """
    def __init__(self, pid, detail_data, attribute_data):
        #: The player's unique in-game player id
        self.pid = int(pid)

        #: The replay.details data on this player
        self.detail_data = detail_data

        #: The replay.attributes.events data on this player
        self.attribute_data = attribute_data

        #: The player result, one of "Win", "Loss", or None
        self.result = None
        if detail_data.result == 1:
            self.result = "Win"
        elif detail_data.result == 2:
            self.result = "Loss"

        #: A reference to the player's :class:`Team` object
        self.team = None

        #: The race the player picked prior to the game starting.
        #: One of Protoss, Terran, Zerg, Random
        self.pick_race = attribute_data.get('Race', 'Unknown')

        #: The difficulty setting for the player. Always Medium for human players.
        #: Very Easy, Easy, Medium, Hard, Harder, Very hard, Elite, Insane,
        #: Cheater 2 (Resources), Cheater 1 (Vision)
        self.difficulty = attribute_data.get('Difficulty', 'Unknown')

        #: The race the player played the game with.
        #: One of Protoss, Terran, Zerg
        self.play_race = LOCALIZED_RACES.get(detail_data.race, detail_data.race)

        #: A reference to a :class:`~sc2reader.utils.Color` object representing the player's color
        self.color = utils.Color(**detail_data.color._asdict())

        #: A list of references to the :class:`~sc2reader.data.Unit` objects the player had this game
        self.units = list()

        #: A list of references to the :class:`~sc2reader.data.Unit` objects that the player killed this game
        self.killed_units = list()

        #: The Battle.net region the entity is registered to
        self.region = GATEWAY_LOOKUP[detail_data.bnet.gateway]

        #: Deprecated, see `Player.region`
        self.gateway = self.region

        #: The Battle.net subregion the entity is registered to
        self.subregion = detail_data.bnet.subregion

        #: The Battle.net acount identifier. Used to construct the
        #: bnet profile url. This value can be zero for games
        #: played offline when a user was not logged in to battle.net.
        self.toon_id = detail_data.bnet.uid


class User(object):
    """
    :param integer uid: The user's unique user id
    :param dict init_data: The init data associated with this user
    """
    #: The Battle.net profile url template
    URL_TEMPLATE = "http://{region}.battle.net/sc2/en/profile/{toon_id}/{subregion}/{name}/"

    def __init__(self, uid, init_data):
        #: The user's unique in-game user id
        self.uid = int(uid)

        #: The replay.initData data on this user
        self.init_data = init_data

        #: The user's Battle.net clan tag at the time of the game
        self.clan_tag = init_data['clan_tag']

        #: The user's Battle.net name at the time of the game
        self.name = init_data['name']

        #: The user's combined Battle.net race levels
        self.combined_race_levels = init_data['combined_race_levels']

        #: The user's highest leauge in the current season
        self.highest_league = init_data['highest_league']

        #: A flag indicating if this person was the one who recorded the game.
        #: This is deprecated because it doesn't actually work.
        self.recorder = None

    @property
    def url(self):
        """The player's formatted Battle.net profile url"""
        return self.URL_TEMPLATE.format(**self.__dict__)


class Observer(Entity, User):
    """ Extends :class:`Entity` and :class:`User`.

    :param integer sid: The entity's unique slot id.
    :param dict slot_data: The slot data associated with this entity
    :param integer uid: The user's unique user id
    :param dict init_data: The init data associated with this user
    :param integer pid: The player's unique player id.
    """
    def __init__(self, sid, slot_data, uid, init_data, pid):
        Entity.__init__(self, sid, slot_data)
        User.__init__(self, uid, init_data)

        #: The player id of the observer. Only meaningful in pre 2.0.4 replays
        self.pid = pid

    def __str__(self):
        return "Observer {0} - {1}".format(self.uid, self.name)


class Computer(Entity, Player):
    """ Extends :class:`Entity` and :class:`Player`

    :param integer sid: The entity's unique slot id.
    :param dict slot_data: The slot data associated with this entity
    :param integer pid: The player's unique player id.
    :param dict detail_data: The detail data associated with this player
    :param dict attribute_data: The attribute data associated with this player
    """
    def __init__(self, sid, slot_data, pid, detail_data, attribute_data):
        Entity.__init__(self, sid, slot_data)
        Player.__init__(self, pid, detail_data, attribute_data)

        #: The auto-generated in-game name for this computer player
        self.name = detail_data.name

    def __str__(self):
        return "Player {0} - {1} ({2})".format(self.pid, self.name, self.play_race)


class Participant(Entity, User, Player):
    """ Extends :class:`Entity`, :class:`User`, and :class:`Player`

    :param integer sid: The entity's unique slot id.
    :param dict slot_data: The slot data associated with this entity
    :param integer uid: The user's unique user id
    :param dict init_data: The init data associated with this user
    :param integer pid: The player's unique player id.
    :param dict detail_data: The detail data associated with this player
    :param dict attribute_data: The attribute data associated with this player
    """
    def __init__(self, sid, slot_data, uid, init_data, pid, detail_data, attribute_data):
        Entity.__init__(self, sid, slot_data)
        User.__init__(self, uid, init_data)
        Player.__init__(self, pid, detail_data, attribute_data)

    def __str__(self):
        return "Player {0} - {1} ({2})".format(self.pid, self.name, self.play_race)


class PlayerSummary():
    """
    Resents a player as loaded from a :class:`~sc2reader.resources.GameSummary`
    file.
    """

    #: The index of the player in the game
    pid = int()

    #: The index of the players team in the game
    teamid = int()

    #: The race the player played in the game.
    play_race = str()

    #: The race the player picked in the lobby.
    pick_race = str()

    #: If the player is a computer
    is_ai = False

    #: If the player won the game
    is_winner = False

    #: Battle.Net id of the player
    bnetid = int()

    #: Subregion id of player
    subregion = int()

    #: The player's gateway, such as us, eu
    gateway = str()

    #: The player's region, such as na, la, eu or ru.  This is
    # provided for convenience, but as of 20121018 is strictly a
    # function of gateway and subregion.
    region = str()

    #: unknown1
    unknown1 = int()

    #: unknown2
    unknown2 = dict()

    #: :class:`Graph` of player army values over time (seconds)
    army_graph = None

    #: :class:`Graph` of player income over time (seconds)
    income_graph = None

    #: Stats from the game in a dictionary
    stats = dict()

    def __init__(self, pid):
        self.unknown2 = dict()
        self.pid = pid

    def __str__(self):
        if not self.is_ai:
            return 'User {0}-S2-{1}-{2}'.format(self.region.upper(), self.subregion, self.bnetid)
        else:
            return 'AI ({0})'.format(self.play_race)

    def __repr__(self):
        return str(self)

    def get_stats(self):
        s = ''
        for k in self.stats:
            s += '{0}: {1}\n'.format(self.stats_pretty_names[k], self.stats[k])
        return s.strip()

BuildEntry = namedtuple('BuildEntry',['supply','total_supply','time','order','build_index'])

# TODO: Are there libraries with classes like this in them
class Graph():
    """
    A class to represent a graph on the score screen. Derived from data in the
    :class:`~sc2reader.resources.GameSummary` file.
    """

    #: Times in seconds on the x-axis of the graph
    times = list()

    #: Values on the y-axis of the graph
    values = list()

    def __init__(self, x, y, xy_list=None):
        self.times = list()
        self.values = list()

        if xy_list:
            for x, y in xy_list:
                self.times.append(x)
                self.values.append(y)
        else:
            self.times = x
            self.values = y

    def as_points(self):
        """ Get the graph as a list of (x, y) tuples """
        return zip(self.times, self.values)

    def __str__(self):
        return "Graph with {0} values".format(len(self.times))

