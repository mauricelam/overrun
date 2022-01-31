'''
Subprocess run tool, that makes the syntax for running a subprocess easier
'''

from contextlib import contextmanager
import subprocess
import string
import sys
import inspect
import shlex


class _ShellQuoteFormatter(string.Formatter):
    '''
    Formats a given string for shell use.

    `None` values are treated like empty strings.
    If shell is True,
        the results are quoted unless the format spec is 'r'
    Otherwise,
        the value is returned
    '''
    def __init__(self, *, shell=False):
        self._shell = shell

    def format_field(self, value, format_spec):
        if value is None:
            str_value = ''
        else:
            str_value = str(value)
        if self._shell:
            if format_spec == 'r':  # raw
                return str_value
            elif format_spec == 'l':  # list
                return ' '.join(shlex.quote(str(v)) for v in value)
            else:
                return shlex.quote(str_value)
        else:
            return str_value


class _SimpleFormatter(string.Formatter):
    '''
    Formats the given string by using the default string.format implementation.
    The output of this formatter returns a string with {0}, {1}, etc, and stores the output in the
    `args` field.
    This formatter must be used with _ShellQuoteFormatter.
    '''

    def __init__(self):
        self.args = []

    def format_field(self, value, format_spec):
        index = len(self.args)
        self.args.append(value)
        if format_spec == 'l':
            return ' '.join(f'{{{index}[{i}]}}' for i in range(len(value)))
        else:
            return f'{{{index}:{format_spec}}}'

    def get_field(self, field_name, args, kwargs):
        value, used_fields = super().get_field(field_name, args, kwargs)
        return value, used_fields


class _EvalFormatter(_SimpleFormatter):
    '''
    Formats the given string by evaluating all of the "fields" as code in its original context,
    making it behave like f-strings.
    The output of this formatter returns a string with {0}, {1}, etc, and stores the output in the
    `args` field.
    This formatter must be used with _ShellQuoteFormatter.
    '''
    def __init__(self, evaluator):
        super().__init__()
        self.evaluator = evaluator

    def get_field(self, field_name, args, kwargs):
        value = self.evaluator(field_name)
        return value, field_name


class CallerEval:
    '''
    Context manager that yields an eval function, which evaluates the given expression in the context
    of the caller (more specifically the caller of `CallerEval()`).
    '''
    def __init__(self):
        self.frame = inspect.currentframe().f_back.f_back

    def _eval(self, expr):
        return eval(expr, self.frame.f_globals, self.frame.f_locals)

    def __enter__(self):
        return self._eval

    def __exit__(self, *exc):
        del self.frame


def cmd(*command, shell=False, evaluator=None, warn_uncalled=True):
    '''
    A command object that can be executed with `.call()`, `.run()`, or `.read()`. The input command
    can one or more strings. Falsy values are filtered out from the list and then joined using with
    a space, i.e. ' '.join(t for t in command if t). This allows for conditional arguments in the
    form of
      cmd('command',
        condition and '--conditional_flag',
        '--cond_flag' if cond else '')

    Any format strings in the form {foo} is evaluated in the caller's context, similar to f-strings.
    The format string can be any valid Python expression, like {foo}, {os.getenv("PWD")}, or
    {1 + 2 + 3}.

    Additionally, a format spec can be given in the form `{foo:r}` for special formats.

    Format specs:
        r - Raw string. Only affects commands with `shell=True`, and strings with this value will be
            inserted verbatim into the shell command without escaping. Read the security
            considerations https://docs.python.org/3/library/subprocess.html#security-considerations
            before proceeding.
        l - List. This is for inserting a list of arguments into the command. The value for this
            format string should be a sequence (e.g. list or tuple), and its values will be inserted
            into the command as separate values.
            e.g. files = [f for f in os.listdir(pwd) if not f.startswith('.')]
                 cmd('grep -e {pattern} {files:l}')

    Note that the string MUST be a literal inside cmd. Accepting it from other function callers will
    cause unintended side effects.

    Good: cmd('echo {name}')
    Bad: cmd(my_command_argument)
    '''
    command = ' '.join(str(t) for t in command if t)
    with (nullcontext(evaluator) if evaluator else CallerEval()) as evaluator:
        return format_cmd(command,
            formatter=_EvalFormatter(evaluator),
            shell=shell,
            warn_uncalled=warn_uncalled)


@contextmanager
def nullcontext(value):
    yield value


def format_cmd(command, *args, formatter=None, shell=False, warn_uncalled=True, **kwargs):
    '''
    Same as `cmd`, but with less magic. Instead of automatically evaluating all of the fields in the
    command, this behaves more like traditional str.format, expecting the field values to be passed
    in through the `args` and `kwargs` of this method.
    '''
    formatter = formatter or _SimpleFormatter()
    first_result = formatter.format(command, *args, **kwargs)
    quote_formatter = _ShellQuoteFormatter(shell=shell)
    if shell:
        second_result = quote_formatter.format(first_result, *formatter.args)
    else:
        second_result = [quote_formatter.format(token, *formatter.args) for token in shlex.split(first_result)]
    return CmdObject(second_result, shell=shell, warn_uncalled=warn_uncalled)


class CmdObject:
    def __init__(self, cmd, *, shell, warn_uncalled=True):
        self._called = not warn_uncalled
        self.cmd = cmd
        self._shell = shell
        self.result = None

    def _call(self, *, verbose=False, silent=False, **kwargs):
        self._called = True
        if verbose:
            print(f'Run command: {self._display_cmd()}', file=sys.stderr)
        if silent:
            kwargs = {
                'stdout': subprocess.DEVNULL,
                'stderr': subprocess.DEVNULL,
                **kwargs
            }
        self.result = CompletedProcess(
            subprocess.run(self.cmd, shell=self._shell, **kwargs))
        return self.result

    def run(self, **kwargs):
        return self._call(**kwargs)

    def call(self, check=True, **kwargs):
        return self._call(check=check, **kwargs)

    def read(self, **kwargs):
        return self.call(stdout=subprocess.PIPE, universal_newlines=True, **kwargs).stdout.rstrip('\n')

    def popen(self, **kwargs):
        self._called = True
        return subprocess.Popen(self.cmd, shell=self._shell, **kwargs)

    def _display_cmd(self):
        return self.cmd

    def __repr__(self):
        return f'CmdObject(cmd={self.cmd})'

    def __del__(self):
        if not self._called:
            print(f'Warning: Uncalled {self}', file=sys.stderr)


class CompletedProcess:

    def __init__(self, completed_process):
        self.completed_process = completed_process
        self._checked = False

    def check_returncode(self):
        self._checked = True
        return self.completed_process.check_returncode()

    def __getattr__(self, name):
        if name == 'returncode':
            self._checked = True
        return getattr(self.completed_process, name)

    def __repr__(self):
        return repr(self.completed_process)

    def __str__(self):
        return str(self.completed_process)

    def __bool__(self):
        try:
            self.check_returncode()
            return True
        except subprocess.CalledProcessError:
            return False

    def __del__(self):
        if not self._checked and not bool(self):
            print(f'Warning: Unchecked failed subprocess: {self}', file=sys.stderr)
