"""Opt-in ordered native sampler profile. This is not a Python token selector."""
import json
import math

CAPABILITY = 'ordered-host-v1'
OPERATORS = {'temperature': ('temperature',), 'min_p': ('min_p',),
             'top_k': ('top_k',), 'top_p': ('top_p',),
             'top_n_sigma': ('top_n_sigma',), 'xtc': ('xtc_probability', 'xtc_threshold')}
RANGES = {'temperature': (0.01, 5), 'min_p': (0, 1), 'top_k': (0, 300000),
          'top_p': (0.000001, 1), 'top_n_sigma': (0, 100),
          'xtc_probability': (0, 1), 'xtc_threshold': (0.000001, 0.5)}
LEGACY = {'temperature', 'top_p', 'top_k', 'min_p', 'presence_penalty',
          'frequency_penalty', 'repetition_penalty', 'penalty_last_n'}


def validate_sampler(req, *, check_conflicts=True):
    misplaced = {'samplers', 'top_n_sigma', 'xtc_probability', 'xtc_threshold', 'dry_multiplier',
                 'dry_base', 'dynatemp_range', 'dynatemp_exponent', 'mirostat', 'mirostat_tau', 'mirostat_eta'} & req.keys()
    if misplaced:
        raise ValueError('unsupported standalone sampler settings; use a supported strata_sampler profile: '
                         + ', '.join(sorted(misplaced)))
    if 'strata_sampler' not in req:
        return None
    value = req['strata_sampler']
    if not isinstance(value, dict):
        raise ValueError('strata_sampler must be an object')
    chain = value.get('chain')
    if not isinstance(chain, list) or not 1 <= len(chain) <= 6 or any(type(s) is not str for s in chain) \
            or len(set(chain)) != len(chain) or set(chain) - OPERATORS.keys() or 'temperature' not in chain:
        raise ValueError('strata_sampler.chain needs unique supported operators and temperature')
    expected = {'chain', 'inspect'} | {p for op in chain for p in OPERATORS[op]}
    if set(value) - expected or expected - {'inspect'} - set(value):
        raise ValueError('strata_sampler needs exactly the parameters used by its chain')
    for key in expected - {'chain', 'inspect'}:
        v = value[key]
        lo, hi = RANGES[key]
        if type(v) not in (int, float) or not math.isfinite(v) or not lo <= v <= hi \
                or key == 'top_k' and type(v) is not int:
            raise ValueError('unsupported strata_sampler value: ' + key)
    if type(value.get('inspect', False)) is not bool:
        raise ValueError('strata_sampler.inspect must be boolean')
    if value.get('inspect') and req.get('logprobs') is not True:
        raise ValueError('strata_sampler.inspect requires logprobs:true for per-token receipts')
    if check_conflicts and LEGACY & req.keys():
        raise ValueError('put all sampler settings inside strata_sampler; only seed stays at top level')
    if req.get('logit_bias') not in (None, {}) or req.get('strata_tune') or req.get('strata_mcp'):
        raise ValueError('strata_sampler does not support logit_bias, native tuning overrides or server MCP')
    if req.get('stop') not in (None, []) or type(req.get('n', 1)) is not int or req.get('n', 1) != 1:
        raise ValueError('strata_sampler supports n:1 and no custom stop strings')
    if req.get('seed') is not None and (type(req['seed']) is not int or not 1 <= req['seed'] < 2**64):
        raise ValueError('strata_sampler seed must be an integer from 1 through 2**64-1')
    return value


def sampler_keys(req):
    value = validate_sampler(req, check_conflicts=False)
    if value is None:
        return ''
    result = ' sampler_chain=' + ','.join(value['chain'])
    for op in value['chain']:
        for key in OPERATORS[op]:
            result += f' sampler_{key}={value[key]!r}'
    return result + (' sampler_inspect=1' if value.get('inspect') else '')


def parse_sampling(line, index):
    try:
        if len(line) > 10000:
            raise ValueError()
        obj = json.loads(line[3:])
        if set(obj) != {'index', 'id', 'probability', 'support', 'entropy', 'stages', 'top', 'selection_ms'}:
            raise ValueError()
        if type(obj['index']) is not int or obj['index'] != index or type(obj['id']) is not int or obj['id'] < 0:
            raise ValueError()
        def number(v, lo, hi):
            return type(v) in (float, int) and math.isfinite(v) and lo <= v <= hi
        def stage(v):
            return type(v['support']) is int and 1 <= v['support'] <= 300000 \
                and number(v['entropy'], 0, 20)
        if not stage(obj) or not number(obj['probability'], 0, 1) or not number(obj['selection_ms'], 0, 1e9):
            raise ValueError()
        if not 2 <= len(obj['stages']) <= 7 or any(set(s) != {'operator', 'support', 'entropy'} or not stage(s)
                or s['operator'] not in {*OPERATORS, 'grammar'} for s in obj['stages']):
            raise ValueError()
        if not 1 <= len(obj['top']) <= 20 or any(set(p) != {'id', 'probability'} or type(p['id']) is not int
                or p['id'] < 0 or not number(p['probability'], 0, 1) for p in obj['top']):
            raise ValueError()
        if len({p['id'] for p in obj['top']}) != len(obj['top']) or len(obj['top']) > obj['support'] \
                or obj['stages'][-1]['support'] != obj['support'] or obj['stages'][-1]['entropy'] != obj['entropy']:
            raise ValueError()
        return obj
    except (ValueError, TypeError, KeyError, OverflowError):
        raise ValueError('invalid native ordered sampler receipt') from None
