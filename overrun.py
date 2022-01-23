'''
Subprocess run tool, that makes the syntax for running a subprocess easier
'''

import subprocess
import string
import os
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
            value = ''
        else:
            value = str(value)
        if self._shell:
            if format_spec == 'r':
                return value
            else:
                print(f'quoting value {value}')
                return shlex.quote(value)
        else:
            return value


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
        return value

    def get_field(self, field_name, args, kwargs):
        index = len(self.args)
        value, used_fields = super().get_field(field_name, args, kwargs)
        self.args.append(value)
        return f'{{{index}}}', used_fields


class _EvalFormatter(string.Formatter):
    '''
    Formats the given string by evaluating all of the "fields" as code in its original context,
    making it behave like f-strings.
    The output of this formatter returns a string with {0}, {1}, etc, and stores the output in the
    `args` field.
    This formatter must be used with _ShellQuoteFormatter.
    '''
    def __init__(self, frame):
        self.frame = frame
        self.args = []

    def format_field(self, value, format_spec):
        return f'{{{value}:{format_spec}}}'

    def get_field(self, field_name, args, kwargs):
        index = len(self.args)
        self.args.append(eval(field_name, self.frame.f_globals, self.frame.f_locals))
        return f'{index}', field_name


def cmd(command, shell=False):
    '''
    A command object that can be executed with `.call()`, `.run()`, or `.read()`. The input command
    can either be a string, or a list of strings. The list of strings will be passed to
    ' '.join(t for t in command if t). This allows for conditional arguments in the form of
      cmd([
        'command',
        condition and '--conditional_flag',
        '--cond_flag' if cond else '',
      ])
    '''
    if isinstance(command, list):
        command = ' '.join(t for t in command if t)
    frame = inspect.currentframe().f_back
    try:
        return format_cmd(command, formatter=_EvalFormatter(frame), shell=shell)
    finally:
        del frame


def format_cmd(command, *args, formatter=None, shell=False, **kwargs):
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
    return CmdObject(second_result, shell=shell)


class CmdObject:
    def __init__(self, cmd, *, shell):
        self._called = False
        self.cmd = cmd
        self._shell = shell
        self.result = None

    def _call(self, *, verbose=False, silent=False, **kwargs):
        self._called = True
        if verbose:
            print(f'Run command: {self._display_cmd()}', file=sys.stderr)
        if silent:
            kwargs['stdout'] = subprocess.DEVNULL
            kwargs['stderr'] = subprocess.DEVNULL
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
        if isinstance(self.cmd, str):
            return self.cmd
        else:
            return ' '.join(shlex.quote(t) for t in self.cmd)

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
