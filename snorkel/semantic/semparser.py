from grammar import Grammar
from ricky import snorkel_rules, snorkel_ops, sem_to_str
from annotator import *

from pandas import DataFrame, Series

class SemanticParser():
    def __init__(self, candidate_class, user_lists={}):
        annotators = [TokenAnnotator(), StopwordAnnotator(), PunctuationAnnotator(), IntegerAnnotator()]
        self.grammar = Grammar(rules=snorkel_rules, 
                               ops=snorkel_ops, 
                               candidate_class=candidate_class,
                               user_lists=user_lists,
                               annotators=annotators)
        self.explanation_counter = 0
        self.LFs = tuple([None] * 6)

    def preprocess(self, explanations):
        for explanation in explanations:
            explanation = explanation.replace("'", '"')
            yield explanation

    def parse(self, explanations, names=None, verbose=False, return_parses=False):
        """
        Accepts natural language explanations and returns parses
        """
        LFs = []
        parses = []
        explanations = explanations if isinstance(explanations, list) else [explanations]
        names = names if isinstance(names, list) else [names]
        for i, exp in enumerate(self.preprocess(explanations)):
            exp_parses = self.grammar.parse_input(exp)
            for j, parse in enumerate(exp_parses):
                # print(parse.semantics)
                lf = self.grammar.evaluate(parse)
                if return_parses:
                    parse.function = lf
                    parses.append(parse)
                if len(names) > i and names[i]:
                    lf.__name__ = "{}_{}".format(names[i], j)
                else:
                    lf.__name__ = "exp%d_%d" % (self.explanation_counter, j)
                LFs.append(lf)
            self.explanation_counter += 1
        if return_parses:
            if verbose:
                print("{} parses created from {} explanations".format(len(LFs), len(explanations)))
            return parses
        else:
            if verbose:
                print("{} LFs created from {} explanations".format(len(LFs), len(explanations)))
            return LFs

    def evaluate(self, 
                examples, 
                show_everything=False,
                show_explanation=False, 
                show_candidate=False,
                show_sentence=False, 
                show_parse=False,
                show_semantics=False,
                show_correct=False,
                show_passing=False, 
                show_failing=False,
                show_redundant=False,
                show_erroring=False,
                show_unknown=False,
                pseudo_python=False,
                remove_paren=False,
                only=[]):
        """Returns a pandas DataFrame with the explanations and various per-explanation stats"""
        if show_everything:
            show_explanation = show_candidate = show_sentence = show_parse = show_semantics = True
        if show_semantics:
            show_correct = show_passing = show_failing = True
            show_redundant = show_erroring = show_unknown = True
        # show_anything = (show_explanation or show_candidate or show_sentence or 
        #                  show_parse or show_semantics or show_correct or 
        #                  show_passing or show_failing or show_redundant or
        #                  show_erroring or show_unknown)
        self.explanation_counter = 0
        examples = examples if isinstance(examples, list) else [examples]
        col_names = ['Correct', 'Passing', 'Failing', 'Redundant', 'Erroring', 'Unknown','Index']
        d = {}
        example_names = []
        indices = []

        nCorrect = [0] * len(examples)
        nPassing = [0] * len(examples)
        nFailing = [0] * len(examples)
        nRedundant = [0] * len(examples)
        nErroring = [0] * len(examples)
        nUnknown = [0] * len(examples)

        correct_LFs = []
        passing_LFs = []
        failing_LFs = []
        redundant_LFs = []
        erroring_LFs = []
        unknown_LFs = []
        
        for i, example in enumerate(examples):
            if only and i not in only:
                continue
            if example.explanation is None:
                continue
            indices.append(i)
            if show_explanation: 
                print("Example {}: {}\n".format(i, example.explanation))
            if show_candidate:
                print("CANDIDATE: {}\n".format(example.candidate))
            if show_sentence:
                print("SENTENCE: {}\n".format(example.candidate[0].get_parent()._asdict()['text']))
            semantics = set()
            explanation = example.explanation
            # TODO: remove remove_paren keyword and code
            if remove_paren:
                explanation = explanation.replace('(', '')
                explanation = explanation.replace(')', '')
            parses = self.parse(
                        explanation, 
                        example.name,
                        return_parses=True)
            # TEMP
            # for parse in self.spurify(parses, spurious_sources=spurious_sources):
            # TEMP
            for parse in parses:
                if show_parse:
                    print("PARSE: {}\n".format(parse))
                semantics_ = sem_to_str(parse.semantics) if pseudo_python else parse.semantics
                # REDUNDANT
                if parse.semantics in semantics:
                    if show_redundant: print("R: {}".format(semantics_))
                    nRedundant[i] += 1
                    redundant_LFs.append(parse.function)
                    continue
                semantics.add(parse.semantics)
                # ERRORING
                try:
                    denotation = parse.function(example.candidate)
                except:
                    if show_erroring: print("E: {}".format(semantics_))
                    print parse.semantics
                    print parse.function(example.candidate) #to display traceback
                    import pdb; pdb.set_trace()
                    nErroring[i] += 1 
                    erroring_LFs.append(parse.function)
                    continue
                # CORRECT             
                if example.semantics and parse.semantics==example.semantics:
                    if show_correct: print("C: {}".format(semantics_))
                    nCorrect[i] += 1
                    LF = parse.function
                    LF.__name__ = LF.__name__[:(LF.__name__).rindex('_')] + '*'
                    correct_LFs.append(parse.function)
                    continue
                # PASSING
                if denotation==example.denotation:
                    if show_passing: print("P: {}".format(semantics_))
                    nPassing[i] += 1
                    passing_LFs.append(parse.function)
                    continue
                else:
                # FAILING
                    if show_failing: print("F: {}".format(semantics_))
                    nFailing[i] += 1
                    failing_LFs.append(parse.function)
                    continue
                # UNKNOWN
                if example.candidate is None:
                    nUnknown[i] += 1
                    unknown_LFs.append(parse.function)
                    continue
                raise Error('This should not be reached.')
                            
            if nCorrect[i] + nPassing[i] == 0:
                print("WARNING: No correct or passing parses found for the following explanation:")
                print("EXPLANATION: {}\n".format(example.explanation))

            if example.name:
                example_names.append(example.name)
            else:
                example_names.append("Example{}".format(i))

        d['Correct'] = Series(data=[nCorrect[i] for i in indices], index=example_names)
        d['Passing'] = Series(data=[nPassing[i] for i in indices], index=example_names)
        d['Failing'] = Series(data=[nFailing[i] for i in indices], index=example_names)
        d['Redundant'] = Series(data=[nRedundant[i] for i in indices], index=example_names)
        d['Erroring'] = Series(data=[nErroring[i] for i in indices], index=example_names)
        d['Unknown'] = Series(data=[nUnknown[i] for i in indices], index=example_names)
        d['Index'] = Series(data=indices, index=example_names)
        
        self.LFs = (correct_LFs, passing_LFs, failing_LFs, redundant_LFs, erroring_LFs, unknown_LFs)
        
        return DataFrame(data=d, index=example_names)[col_names]

    # def spurify(self, parses, spurious_sources={}):
    #     """
    #     spurious_sources[key] = x
    #     key: one of ['compare_op_swap', 'binary_op_swap', 'logic_op_swap', 
    #                 'grouping', 'split_compound', 'off_by_one']
    #     x: percentage of parses to be mutated by that spurious source
    #     """        
    #     compare_ops = ['.eq','.neq','.lt','.leq','.geq','.gt']
    #     for parse in parses:
    #         import pdb; pdb.set_trace()
    #         yield parse
    #         # determine which sources to use
    #         for (source, prob) in spurious_sources.items():
    #             if np.random.random() < prob:
    #                 if source == 'compare_op_swap':

    #                     op = parse.semantics[0]
    #                     args = parse.semantics[1:]
    #                     if op in compare_ops:
    #                         print(parse.semantics)
    #                         parse

    #                     if parse.rule

    #                 if self.rule.is_lexical():
    #                     return self.rule.sem
    #                 else:
    #                     child_semantics = [child.semantics for child in self.children]
    #                     return self.rule.apply_semantics(child_semantics)
    #                 lf = self.grammar.evaluate(parse)
    #                 parse.function = lf
    #                 yield parse
    #         import pdb; pdb.set_trace()
        
    #     def __init__(self, rule, children):
    #     self.rule = rule
    #     self.children = tuple(children[:])
    #     self.semantics = self.compute_semantics()
    #     self.validate_parse()