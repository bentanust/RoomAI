#!/bin/python
#coding:utf-8

import roomai.abstract
import random
import copy
import itertools

from roomai.doudizhu.DouDiZhuPokerInfo   import *
from roomai.doudizhu.DouDiZhuPokerAction import *

class DouDiZhuPokerEnv(roomai.common.AbstractEnv):

    def __init__(self):
        self.public_state  = DouDiZhuPublicState()
        self.private_state = DouDiZhuPrivateState()
        self.person_states = [DouDiZhuPersonState() for i in range(3)]


    def generate_initial_cards(self):

        cards = []
        for i in range(13):
            for j in range(4):
                cards.append(DouDiZhuActionElement.rank_to_str[i])
        cards.append(DouDiZhuActionElement.rank_to_str[13])
        cards.append(DouDiZhuActionElement.rank_to_str[14])
        random.shuffle(cards)

        for i in range(3):
            tmp = cards[i*17:(i+1)*17]
            tmp.sort()
            self.person_states[i].hand_cards = DouDiZhuHandCards("".join(tmp))

        keep_cards = DouDiZhuHandCards([cards[-1], cards[-2], cards[-3]])
        self.private_state.keep_cards =  keep_cards;

    def update_license(self, turn, action):
        if action.pattern[0] != "i_cheat":
            self.public_state.license_playerid = turn
            self.public_state.license_action   = action 
            

    def update_cards(self, turn, action):
        self.person_states[turn].hand_cards.remove_action_cards(action)


    def update_phase_bid2play(self):
        self.public_state.phase            = PhaseSpace.play
        
        self.public_state.landlord_id      = self.public_state.landlord_candidate_id
        self.public_state.license_playerid = self.public_state.turn        

        landlord_id = self.public_state.landlord_id
        self.private_state.hand_cards[landlord_id].add_cards(self.private_state.keep_cards)


    #@Overide
    def init(self):

        ## init the info
        
        self.generate_initial_cards()
        
        self.public_state.firstPlayer       = int(random.random() * 3)
        self.public_state.turn              = self.public_state.firstPlayer
        self.public_state.phase             = PhaseSpace.bid
        self.public_state.epoch             = 0
        
        self.public_state.landlord_id         = -1
        self.public_state.license_playerid    = self.public_state.turn
        self.public_state.license_action      = None
        self.public_state.is_terminal         = False
        self.public_state.scores              = [0,0,0]

        turn = self.public_state.turn
        self.person_states[turn].available_actions = DouDiZhuPokerEnv.available_actions(self.public_state, self.person_states[turn])

        infos = self.__gen_infos__()
        self.__gen_history__()

        return infos, self.public_state, self.person_states, self.private_state


    ## we need ensure the action is valid
    #@Overide
    def forward(self, action):

        turn = self.public_state.turn
        if self.public_state.phase == 0:
            if action.pattern[0] == "i_bid":
                self.public_state.landlord_candidate_id = turn

            if self.public_state.epoch == 3 and self.public_state.landlord_candidate_id == -1:
                self.public_state.is_terminal = True
                self.public_state.scores      = [0.0, 0.0, 0.0]

                self.__gen_history__()
                infos = self.__gen_infos__()
                return infos, self.public_state, self.person_states, self.private_state

            if (self.public_state.epoch == 2 and self.public_state.landlord_candidate_id != -1)\
                or self.public_state.epoch == 3:
                self.update_phase_bid2play()
                self.person_states[self.public_state.landlord_id].hand_cards.add_cards(self.private_state.keep_cards)

        else: #phase == play

            if action.pattern[0] != "i_cheat":
                
                self.update_cards(turn,action)
                self.update_license(turn,action)
                self.public_state.continous_cheat_num = 0
    
                num = self.person_states[turn].hand_cards.num_cards
                if num == 0:
                    self.public_state.previous_id = turn
                    self.public_state.previous_action = action
                    self.public_state.epoch += 1
                    if turn == self.public_state.landlord_id:
                        self.public_state.is_terminal                           = True
                        self.public_state.scores                                = [-1,-1,-1]
                        self.public_state.scores[self.public_state.landlord_id] = 2
                    else:
                        self.public_state.is_terminal                           = True
                        self.public_state.scores                                = [1,1,1]
                        self.public_state.scores[self.public_state.landlord_id] = -2
                    self.__gen_history__()
                    infos = self.__gen_infos__()
                    return infos, self.public_state, self.person_states, self.private_state
            else:
                self.public_state.continous_cheat_num += 1

        if (self.public_state.epoch == 2 and self.public_state.landlord_candidate_id != -1) \
            or self.public_state.epoch == 3:pass
        else:
            self.public_state.turn   = (turn+1)%3

        if self.public_state.continous_cheat_num == 2:
            self.public_state.is_response = False
        else:
            self.public_state.is_response = True
        self.public_state.continous_cheat_num = 0

        self.public_state.previous_id         = turn
        self.public_state.previous_action     = action
        self.public_state.epoch              += 1
        self.person_states[self.public_state.turn].available_actions = DouDiZhuPokerEnv.available_actions(self.public_state, self.person_states[self.public_state.turn])
         
        self.__gen_history__()
        infos = self.__gen_infos__()

        return infos, self.public_state, self.person_states, self.private_state


    #@override
    @classmethod
    def compete(cls, env, players):
        infos ,public_state, person_states, private_state= env.init()

        for i in range(len(players)):
            players[i].receive_info(infos[i])

        while public_state.is_terminal == False:
            turn = public_state.turn
            action = players[turn].takeAction()
            infos, public_state, person_states, private_state = env.forward(action)
            for i in range(len(players)):
                players[i].receive_info(infos[i])

        return public_state.scores



    @classmethod
    def available_actions(cls, public_state, person_state):

        patterns = []
        if public_state.phase == 0:
            patterns.append(AllPatterns["i_cheat"])
            patterns.append(AllPatterns["i_bid"])
        else:
            if public_state.is_response == False:
                for p in AllPatterns:
                    if p != "i_cheat" and p != "i_invalid":
                        patterns.append(AllPatterns[p])
            else:
                patterns.append(public_state.license_action.pattern)
                if public_state.license_action.pattern[6] == 1:
                    patterns.append(AllPatterns["p_4_1_0_0_0"])  # rank = 10
                    patterns.append(AllPatterns["x_rocket"])  # rank = 100
                if public_state.license_action.pattern[6] == 10:
                    patterns.append(AllPatterns["x_rocket"])  # rank = 100
                patterns.append(AllPatterns["i_cheat"])

        is_response = public_state.is_response
        license_act = public_state.license_action
        actions = dict()

        for pattern in patterns:
            numMaster = pattern[1]
            numMasterPoint = pattern[2]
            isStraight = pattern[3]
            numSlave = pattern[4]
            MasterCount = -1
            SlaveCount = -1

            if numMaster > 0:
                MasterCount = int(numMaster / numMasterPoint)

            if "i_invalid" == pattern[0]:
                continue

            if "i_cheat" == pattern[0]:
                action_key = cls.master_slave_cards_to_key([DouDiZhuActionElement.cheat], [])
                action     = DouDiZhuAction.lookup(action_key)
                if cls.is_action_valid(person_state.hand_cards, public_state, action) == True:
                    actions[action_key] = action
                continue

            if "i_bid" == pattern[0]:
                action_key = cls.master_slave_cards_to_key([DouDiZhuActionElement.bid], [])
                action     = DouDiZhuAction.lookup(action_key)
                if cls.is_action_valid(person_state.hand_cards, public_state, action) == True:
                    actions[action_key] = action
                continue

            if pattern[0] == "x_rocket":
                if person_state.hand_cards.cards[DouDiZhuActionElement.r] == 1 and \
                                person_state.hand_cards.cards[DouDiZhuActionElement.R] == 1:
                    action_key  = cls.master_slave_cards_to_key([DouDiZhuActionElement.r, DouDiZhuActionElement.R], [])
                    action      = DouDiZhuAction.lookup(action_key)
                    if cls.is_action_valid(person_state.hand_cards, public_state, action) == True:
                        actions[action_key] = action
                continue

            if pattern[1] + pattern[4] > person_state.hand_cards.num_cards:
                continue
            sum1 = 0

            for count in range(MasterCount, 5, 1):
                sum1 += person_state.hand_cards.count2num[count]
            if sum1 < numMasterPoint:
                continue

            ### action with cards
            mCardss = []
            mCardss = DouDiZhuPokerEnv.extractMasterCards(person_state.hand_cards, numMasterPoint, MasterCount, pattern)

            for mCards in mCardss:
                if numSlave == 0:
                    action_key   = cls.master_slave_cards_to_key(mCards, [])
                    action       = DouDiZhuAction.lookup(action_key)
                    if cls.is_action_valid(person_state.hand_cards, public_state, action) == True:
                        actions[action_key] = action
                    continue

                sCardss = DouDiZhuPokerEnv.extractSlaveCards(person_state.hand_cards, numSlave, mCards, pattern)
                for sCards in sCardss:
                    action_key  = cls.master_slave_cards_to_key(mCards, sCards)
                    action      = DouDiZhuAction.lookup(action_key)
                    if cls.is_action_valid(person_state.hand_cards, public_state, action) == True:
                        actions[action_key] = action
        return actions



    @classmethod
    def is_action_valid(cls, hand_cards, public_state, action):
        if cls.gen_allactions == True:
            return True

        if action.pattern[0] == "i_invalid":
            return False

        if Utils.is_action_from_handcards(hand_cards, action) == False:
            return False

        turn = public_state.turn
        license_id = public_state.license_playerid
        license_act = public_state.license_action
        phase = public_state.phase

        if phase == 0:
            if action.pattern[0] not in ["i_cheat", "i_bid"]:
                return False
            return True

        if phase == 1:
            if action.pattern[0] == "i_bid":    return False

            if public_state.is_response == False:
                if action.pattern[0] == "i_cheat": return False
                return True

            else:  # response
                if action.pattern[0] == "i_cheat":  return True
                ## not_cheat
                if action.pattern[6] > license_act.pattern[6]:
                    return True
                elif action.pattern[6] < license_act.pattern[6]:
                    return False
                elif action.maxMasterPoint - license_act.maxMasterPoint > 0:
                    return True
                else:
                    return False

    @classmethod
    def is_action_from_handcards(cls, hand_cards, action):
        flag = True
        if action.pattern[0] == "i_cheat":  return True
        if action.pattern[0] == "i_bid":    return True
        if action.pattern[0] == "i_invalid":    return False

        for a in action.masterPoints2Count:
            flag = flag and (action.masterPoints2Count[a] <= hand_cards.cards[a])
        for a in action.slavePoints2Count:
            flag = flag and (action.slavePoints2Count[a] <= hand_cards.cards[a])
        return flag


    @classmethod
    def extractMasterCards(cls, hand_cards, numPoint, count, pattern):
        is_straight = pattern[3]
        cardss = []
        ss = []

        if numPoint == 0:
            return cardss

        if is_straight == 1:
            c = 0
            for i in range(11, -1, -1):
                if hand_cards.cards[i] >= count:
                    c += 1
                else:
                    c = 0

                if c >= numPoint:
                    ss.append(range(i, i + numPoint))
        else:
            candidates = []
            for c in range(len(hand_cards.cards)):
                if hand_cards.cards[c] >= count:
                    candidates.append(c)
            if len(candidates) < numPoint:
                return []
            ss = list(itertools.combinations(candidates, numPoint))

        for set1 in ss:
            s = []
            for c in set1:
                for i in range(count):
                    s.append(c)
            s.sort()
            cardss.append(s)

        return cardss

    @classmethod
    def extractSlaveCards(cls, hand_cards, numCards, used_cards, pattern):
        used = [0 for i in range(15)]
        for p in used_cards:
            used[p] += 1

        numMaster = pattern[1]
        numMasterPoint = pattern[2]
        numSlave = pattern[4]

        candidates = []
        res1 = []
        res = []

        if numMaster / numMasterPoint == 3:
            if numSlave / numMasterPoint == 1:  # single
                for c in range(len(hand_cards.cards)):
                    if used[c] == 0 and ((hand_cards.cards[c] - used[c])) >= 1:
                        candidates.append(c)
                if len(candidates) >= numCards:
                    res1 = list(set(list(itertools.combinations(candidates, numCards))))
                for sCard in res1:  res.append([x for x in sCard])

            elif numSlave / numMasterPoint == 2:  # pair
                for c in range(len(hand_cards.cards)):
                    if (hand_cards.cards[c] - used[c]) >= 2 and used[c] == 0:
                        candidates.append(c)
                if len(candidates) >= numCards / 2:
                    res1 = list(set(list(itertools.combinations(candidates, int(numCards / 2)))))
                for sCard in res1:
                    tmp = [x for x in sCard]
                    tmp.extend([x for x in sCard])
                    res.append(tmp)

        elif numMaster / numMasterPoint == 4:

            if numSlave / numMasterPoint == 2:  # single
                for c in range(len(hand_cards.cards)):
                    if used[c] == 0 and (hand_cards.cards[c] - used[c]) >= 1:
                        candidates.append(c)
                if len(candidates) >= numCards:
                    res1 = list(set(list(itertools.combinations(candidates, numCards))))
                for sCard in res1:  res.append([x for x in sCard])


            elif numSlave / numMasterPoint == 4:  # pair
                for c in range(len(hand_cards.cards)):
                    if (hand_cards.cards[c] - used[c]) >= 2 and used[c] == 0:
                        candidates.append(c)
                if len(candidates) >= numCards / 2:
                    res1 = list(set(list(itertools.combinations(candidates, int(numCards / 2)))))
                for sCard in res1:
                    tmp = [x for x in sCard]
                    tmp.extend([x for x in sCard])
                    res.append(tmp)

        return res

