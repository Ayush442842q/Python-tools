#!/usr/bin/env python3
"""
Regex NFA/DFA State Machine Visualizer
Parses basic regular expressions and compiles them into a Non-deterministic Finite
Automaton (NFA) using Thompson's construction, then converts it to a Deterministic
Finite Automaton (DFA) using subset construction.
Generates Mermaid.js flowchart syntax to visualize state machines.
Uses standard libraries only.
"""

import argparse
import sys
from typing import Dict, List, Set, Tuple, Any

# Special symbol for Epsilon (empty string transition)
EPSILON = 'ε'

class State:
    """Represents a state in an NFA or DFA."""
    def __init__(self, state_id: int):
        self.id = state_id
        # Transitions mapping: input_symbol -> List of target States
        self.transitions: Dict[str, List['State']] = {}

    def add_transition(self, symbol: str, target: 'State'):
        if symbol not in self.transitions:
            self.transitions[symbol] = []
        self.transitions[symbol].append(target)


class NFA:
    """Represents a Non-deterministic Finite Automaton."""
    def __init__(self, start: State, accept: State):
        self.start = start
        self.accept = accept

    def get_all_states(self) -> Set[State]:
        """Traverses the NFA and returns all unique states."""
        visited = set()
        to_visit = [self.start]
        while to_visit:
            curr = to_visit.pop(0)
            if curr not in visited:
                visited.add(curr)
                for targets in curr.transitions.values():
                    for target in targets:
                        to_visit.append(target)
        return visited


class RegexParser:
    """Helper to convert regex infix notation to postfix (Reverse Polish) notation."""
    def __init__(self):
        self.precedence = {'*': 4, '+': 4, '?': 4, '.': 3, '|': 2, '(': 1}

    def _insert_concat_operators(self, regex: str) -> str:
        """Inserts explicit concat dots '.' where concatenation is implicit."""
        result = []
        operators = {'|', '(', ')'}
        unary_operators = {'*', '+', '?'}
        
        for i in range(len(regex)):
            c1 = regex[i]
            result.append(c1)
            
            if i + 1 < len(regex):
                c2 = regex[i + 1]
                
                # Insert concat dot if:
                # 1. c1 is a character or a unary op (like *, +, ?) AND c2 is a character or '('
                is_c1_operand = (c1 not in operators and c1 not in unary_operators) or c1 in unary_operators or c1 == ')'
                is_c2_operand = (c2 not in operators and c2 not in unary_operators) or c2 == '('
                
                if is_c1_operand and is_c2_operand:
                    result.append('.')
                    
        return ''.join(result)

    def to_postfix(self, regex: str) -> str:
        """Shunting-yard algorithm to convert infix regex to postfix RPN."""
        if not regex:
            return ""
            
        formatted = self._insert_concat_operators(regex)
        output = []
        stack = []
        
        for char in formatted:
            if char == '(':
                stack.append(char)
            elif char == ')':
                while stack and stack[-1] != '(':
                    output.append(stack.pop())
                if stack:
                    stack.pop() # Remove '('
            elif char in self.precedence:
                while stack and self.precedence.get(stack[-1], 0) >= self.precedence[char]:
                    output.append(stack.pop())
                stack.append(char)
            else:
                # Ordinary operand character
                output.append(char)
                
        while stack:
            output.append(stack.pop())
            
        return ''.join(output)


class ThompsonConstruction:
    """Compiles postfix regex to NFA using Thompson's construction."""
    def __init__(self):
        self.state_counter = 0

    def _new_state(self) -> State:
        state = State(self.state_counter)
        self.state_counter += 1
        return state

    def build_nfa(self, postfix_regex: str) -> NFA:
        if not postfix_regex:
            s = self._new_state()
            return NFA(s, s)
            
        stack: List[NFA] = []
        
        for char in postfix_regex:
            if char == '.':
                # Concat: pop NFA2, NFA1; connect NFA1 accept to NFA2 start
                nfa2 = stack.pop()
                nfa1 = stack.pop()
                
                nfa1.accept.add_transition(EPSILON, nfa2.start)
                stack.append(NFA(nfa1.start, nfa2.accept))
                
            elif char == '|':
                # Alternation: pop NFA2, NFA1; build new start & accept
                nfa2 = stack.pop()
                nfa1 = stack.pop()
                
                start = self._new_state()
                accept = self._new_state()
                
                start.add_transition(EPSILON, nfa1.start)
                start.add_transition(EPSILON, nfa2.start)
                nfa1.accept.add_transition(EPSILON, accept)
                nfa2.accept.add_transition(EPSILON, accept)
                
                stack.append(NFA(start, accept))
                
            elif char == '*':
                # Kleene Star: pop NFA; build new start & accept
                nfa = stack.pop()
                
                start = self._new_state()
                accept = self._new_state()
                
                start.add_transition(EPSILON, nfa.start)
                start.add_transition(EPSILON, accept)
                nfa.accept.add_transition(EPSILON, nfa.start)
                nfa.accept.add_transition(EPSILON, accept)
                
                stack.append(NFA(start, accept))
                
            elif char == '+':
                # Plus (one or more): pop NFA; build new start & accept
                nfa = stack.pop()
                
                start = self._new_state()
                accept = self._new_state()
                
                start.add_transition(EPSILON, nfa.start)
                nfa.accept.add_transition(EPSILON, nfa.start)
                nfa.accept.add_transition(EPSILON, accept)
                
                stack.append(NFA(start, accept))
                
            elif char == '?':
                # Optional (zero or one): pop NFA; build new start & accept
                nfa = stack.pop()
                
                start = self._new_state()
                accept = self._new_state()
                
                start.add_transition(EPSILON, nfa.start)
                start.add_transition(EPSILON, accept)
                nfa.accept.add_transition(EPSILON, accept)
                
                stack.append(NFA(start, accept))
                
            else:
                # Literal character: build simple state-to-state NFA
                start = self._new_state()
                accept = self._new_state()
                start.add_transition(char, accept)
                stack.append(NFA(start, accept))
                
        return stack.pop()


# --- DFA Subset Construction ---

def epsilon_closure(states: Set[State]) -> Set[State]:
    """Finds all states reachable from input set using only EPSILON transitions."""
    closure = set(states)
    stack = list(states)
    
    while stack:
        curr = stack.pop()
        for target in curr.transitions.get(EPSILON, []):
            if target not in closure:
                closure.add(target)
                stack.append(target)
                
    return closure

def nfa_move(states: Set[State], symbol: str) -> Set[State]:
    """Finds all states reachable from input set using a transition on symbol."""
    reachable = set()
    for s in states:
        for target in s.transitions.get(symbol, []):
            reachable.add(target)
    return reachable


class DFAState:
    """Represents a state in the Deterministic Finite Automaton, wrapping a set of NFA states."""
    def __init__(self, state_id: int, nfa_states: Set[State]):
        self.id = state_id
        self.nfa_states = nfa_states
        # Transitions: symbol -> DFAState
        self.transitions: Dict[str, 'DFAState'] = {}
        self.is_accept = False


class DFA:
    """Represents a Deterministic Finite Automaton."""
    def __init__(self, start: DFAState):
        self.start = start

    def get_all_states(self) -> Set[DFAState]:
        visited = set()
        to_visit = [self.start]
        while to_visit:
            curr = to_visit.pop(0)
            if curr not in visited:
                visited.add(curr)
                for target in curr.transitions.values():
                    to_visit.append(target)
        return visited


def convert_nfa_to_dfa(nfa: NFA) -> DFA:
    """Converts NFA to DFA using subset construction."""
    # Find all alphabet symbols in NFA (except EPSILON)
    alphabet = set()
    for s in nfa.get_all_states():
        for sym in s.transitions.keys():
            if sym != EPSILON:
                alphabet.add(sym)
                
    state_id = 0
    # Map NFA state set (frozen) to DFAState
    dfa_states: Dict[frozenset, DFAState] = {}
    
    # 1. Compute start state closure
    start_closure = epsilon_closure({nfa.start})
    start_dfa = DFAState(state_id, start_closure)
    state_id += 1
    
    start_key = frozenset(start_closure)
    dfa_states[start_key] = start_dfa
    
    # Flag accept states
    if nfa.accept in start_closure:
        start_dfa.is_accept = True
        
    unmarked = [start_dfa]
    
    while unmarked:
        curr_dfa = unmarked.pop(0)
        
        for symbol in sorted(alphabet):
            # Compute move and epsilon closure
            moved = nfa_move(curr_dfa.nfa_states, symbol)
            closure = epsilon_closure(moved)
            
            if not closure:
                continue
                
            closure_key = frozenset(closure)
            
            if closure_key not in dfa_states:
                new_dfa = DFAState(state_id, closure)
                state_id += 1
                if nfa.accept in closure:
                    new_dfa.is_accept = True
                dfa_states[closure_key] = new_dfa
                unmarked.append(new_dfa)
                
            curr_dfa.transitions[symbol] = dfa_states[closure_key]
            
    return DFA(start_dfa)


# --- Visualization Formatting (Mermaid.js) ---

def generate_mermaid_nfa(nfa: NFA) -> str:
    """Generates Mermaid flowchart code for NFA."""
    lines = ["graph LR", "    classDef start fill:#f9f,stroke:#333,stroke-width:2px;", "    classDef accept fill:#9f9,stroke:#333,stroke-width:4px;"]
    
    # Start and Accept indicators
    lines.append(f"    S((Start)) --> q{nfa.start.id}")
    lines.append(f"    class q{nfa.start.id} start")
    lines.append(f"    class q{nfa.accept.id} accept")
    
    all_states = sorted(list(nfa.get_all_states()), key=lambda x: x.id)
    
    for s in all_states:
        # Build transitions
        for sym, targets in s.transitions.items():
            for t in targets:
                # Use double-circle shape for accept state
                shape_s = f"((q{s.id}))" if s.id == nfa.accept.id else f"(q{s.id})"
                shape_t = f"((q{t.id}))" if t.id == nfa.accept.id else f"(q{t.id})"
                lines.append(f"    q{s.id}{shape_s} -- \"{sym}\" --> q{t.id}{shape_t}")
                
    return '\n'.join(lines)


def generate_mermaid_dfa(dfa: DFA) -> str:
    """Generates Mermaid flowchart code for DFA."""
    lines = ["graph LR", "    classDef start fill:#f9f,stroke:#333,stroke-width:2px;", "    classDef accept fill:#9f9,stroke:#333,stroke-width:4px;"]
    
    # Start and Accept indicators
    lines.append(f"    S((Start)) --> D{dfa.start.id}")
    lines.append(f"    class D{dfa.start.id} start")
    
    all_states = sorted(list(dfa.get_all_states()), key=lambda x: x.id)
    
    for s in all_states:
        if s.is_accept:
            lines.append(f"    class D{s.id} accept")
            
        for sym, target in s.transitions.items():
            shape_s = f"((D{s.id}))" if s.is_accept else f"(D{s.id})"
            shape_t = f"((D{target.id}))" if target.is_accept else f"(D{target.id})"
            
            # Map subset details as tooltip
            label_s = f"D{s.id} [{{{','.join(str(n.id) for n in sorted(list(s.nfa_states), key=lambda x:x.id))}}}]"
            label_t = f"D{target.id} [{{{','.join(str(n.id) for n in sorted(list(target.nfa_states), key=lambda x:x.id))}}}]"
            
            lines.append(f"    D{s.id}{shape_s} -- \"{sym}\" --> D{target.id}{shape_t}")
            
    return '\n'.join(lines)


# --- Simulation / Validation Testing ---

def simulate_dfa(dfa: DFA, string: str) -> Tuple[bool, List[str]]:
    """Simulates DFA matching. Returns (matches_fully, step_history)."""
    curr = dfa.start
    history = [f"Start state: D{curr.id}"]
    
    for char in string:
        if char in curr.transitions:
            next_state = curr.transitions[char]
            history.append(f"Read '{char}': D{curr.id} -> D{next_state.id}")
            curr = next_state
        else:
            history.append(f"Read '{char}': No transition from D{curr.id}. Rejected!")
            return False, history
            
    if curr.is_accept:
        history.append(f"Finished at accepting state: D{curr.id}. Accepted!")
        return True, history
    else:
        history.append(f"Finished at non-accepting state: D{curr.id}. Rejected!")
        return False, history


def main():
    parser = argparse.ArgumentParser(
        description="Regex NFA/DFA State Machine Builder & Visualizer - Compile regex to state graphs."
    )
    parser.add_argument("regex", help="Regular expression pattern (supports: a-z, |, *, +, ?, ( ))")
    parser.add_argument(
        "-t", "--type",
        choices=["nfa", "dfa", "both"],
        default="both",
        help="Visualization type (default: both)"
    )
    parser.add_argument(
        "--test",
        help="Test input string against the regex and show trace history"
    )
    parser.add_argument(
        "-m", "--mermaid",
        action="store_true",
        help="Only output raw Mermaid code (easy for copy-pasting into editors)"
    )

    args = parser.parse_args()

    # 1. Parse Infix to Postfix RPN
    parser_engine = RegexParser()
    try:
        postfix = parser_engine.to_postfix(args.regex)
    except Exception as e:
        print(f"[-] Invalid regular expression syntax: {e}", file=sys.stderr)
        return 1
        
    # 2. Thompson Construction NFA
    nfa_builder = ThompsonConstruction()
    nfa = nfa_builder.build_nfa(postfix)
    
    # 3. Subset Construction DFA
    dfa = convert_nfa_to_dfa(nfa)

    if args.mermaid:
        if args.type == "nfa":
            print(generate_mermaid_nfa(nfa))
        elif args.type == "dfa":
            print(generate_mermaid_dfa(dfa))
        else:
            print("%% --- NFA Diagram ---")
            print(generate_mermaid_nfa(nfa))
            print("\n%% --- DFA Diagram ---")
            print(generate_mermaid_dfa(dfa))
        return 0

    print("=================================================================")
    print(f"[*] Regex Pattern: {args.regex}")
    print(f"[*] Postfix RPN  : {postfix}")
    print(f"[*] NFA States   : {len(nfa.get_all_states())}")
    print(f"[*] DFA States   : {len(dfa.get_all_states())}")
    print("=================================================================")

    # Print Text NFA Transitions
    if args.type in ("nfa", "both"):
        print("\n--- NFA Transition Table ---")
        for s in sorted(list(nfa.get_all_states()), key=lambda x: x.id):
            transitions_str = []
            for sym, targets in s.transitions.items():
                targets_str = ",".join(f"q{t.id}" for t in targets)
                transitions_str.append(f"'{sym}'->({targets_str})")
            print(f"State q{s.id:2d} [{'Accept' if s.id == nfa.accept.id else '      '}]: {', '.join(transitions_str)}")

    # Print Text DFA Transitions
    if args.type in ("dfa", "both"):
        print("\n--- DFA Transition Table ---")
        for s in sorted(list(dfa.get_all_states()), key=lambda x: x.id):
            transitions_str = []
            for sym, target in s.transitions.items():
                transitions_str.append(f"'{sym}'->D{target.id}")
            nfa_subset = f"{{{','.join(str(n.id) for n in sorted(list(s.nfa_states), key=lambda x:x.id))}}}"
            print(f"State D{s.id:2d} [{'Accept' if s.is_accept else '      '}] NFA subset: {nfa_subset:12s} Transitions: {', '.join(transitions_str)}")

    # Print Mermaid diagram code
    print("\n--- Mermaid diagram source codes ---")
    if args.type in ("nfa", "both"):
        print("\n```mermaid\n%% NFA Diagram")
        print(generate_mermaid_nfa(nfa))
        print("```")
        
    if args.type in ("dfa", "both"):
        print("\n```mermaid\n%% DFA Diagram")
        print(generate_mermaid_dfa(dfa))
        print("```")

    # Run Simulation
    if args.test is not None:
        print("\n=================================================================")
        print(f"[*] Simulating DFA match for: '{args.test}'")
        matched, trace = simulate_dfa(dfa, args.test)
        print("-----------------------------------------------------------------")
        for step in trace:
            print(f"  {step}")
        print("-----------------------------------------------------------------")
        print(f"[#] Match Status: {'[ACCEPTED]' if matched else '[REJECTED]'}")
        print("=================================================================")

    return 0

if __name__ == "__main__":
    sys.exit(main())
