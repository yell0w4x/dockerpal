"""Reconstruct an approximate Dockerfile from an image's history.

Docker does not keep the Dockerfile an image was built from; all that survives
is the command recorded for each layer. That is enough to recover most
instructions, but not the contents of ADD/COPY, and BuildKit records less than
the classic builder did, so the result is a readable approximation.
"""

import re


NOP = '#(nop)'
SHELL_PREFIX = '/bin/sh -c '
BUILDKIT_MARKER = re.compile(r'\s*#\s*buildkit\s*$')
# History records RUN layers as '|<n> ARG=val ... /bin/sh -c <command>'.
BUILD_ARGS = re.compile(r'^\|\d+\s+(?:\S+=\S*\s+)*')
# ...ports as Go's map formatting, and exec forms without their commas.
GO_MAP = re.compile(r'^map\[(.*)\]$')
EXEC_FORM = re.compile(r'"\s+"')

# Instructions whose argument is a JSON array in a real Dockerfile.
EXEC_INSTRUCTIONS = frozenset(('CMD', 'ENTRYPOINT', 'SHELL', 'VOLUME'))

INSTRUCTIONS = frozenset((
    'ADD', 'ARG', 'CMD', 'COPY', 'ENTRYPOINT', 'ENV', 'EXPOSE', 'FROM',
    'HEALTHCHECK', 'LABEL', 'MAINTAINER', 'ONBUILD', 'RUN', 'SHELL',
    'STOPSIGNAL', 'USER', 'VOLUME', 'WORKDIR',
))

HEADER = (
    '# Reconstructed by dockerpal from the image history.',
    '# ADD/COPY contents are not stored in the image, and layers built with',
    '# BuildKit record less detail, so this is an approximation.',
)


def instruction(created_by):
    """Turn one history entry's command into a Dockerfile line, or None."""

    text = (created_by or '').strip()
    if not text:
        return None

    text = BUILDKIT_MARKER.sub('', text).strip()
    if NOP in text:
        return _tidy(text.split(NOP, 1)[1].strip()) or None

    text = BUILD_ARGS.sub('', text)
    keyword, _, rest = text.partition(' ')
    if keyword.upper() in INSTRUCTIONS:
        if keyword.upper() == 'RUN':
            # BuildKit writes 'RUN |<n> ARG=val ... /bin/sh -c <command>'.
            rest = BUILD_ARGS.sub('', rest)
            if rest.startswith(SHELL_PREFIX):
                rest = rest[len(SHELL_PREFIX):]
            return f'RUN {rest.strip()}'
        return _tidy(text)
    if text.startswith(SHELL_PREFIX):
        return f'RUN {text[len(SHELL_PREFIX):].strip()}'

    return f'RUN {text}' if text else None


def _tidy(text):
    """Undo the Go formatting docker history uses for some arguments."""

    keyword, _, rest = text.partition(' ')
    keyword = keyword.upper()
    rest = rest.strip()

    if keyword == 'EXPOSE':
        ports = GO_MAP.match(rest)
        if ports:
            rest = ' '.join(port.split(':')[0] for port in ports.group(1).split())
        return f'EXPOSE {rest}'

    if keyword in EXEC_INSTRUCTIONS and rest.startswith('['):
        argv = EXEC_FORM.sub('", "', rest)
        return f'{keyword} {argv}'

    return text


def from_history(entries, image_ref=None):
    """Build the Dockerfile text for a docker history listing (newest first)."""

    lines = [f'# {image_ref}'] if image_ref else []
    lines.extend(HEADER)

    instructions = [i for i in (instruction(e.get('CreatedBy')) for e in reversed(entries)) if i]
    if not instructions or not instructions[0].upper().startswith('FROM'):
        instructions.insert(0, 'FROM scratch')
    lines.extend(instructions)

    return '\n'.join(lines) + '\n'
