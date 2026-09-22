from dockerpal.dockerfile import from_history, instruction


def test_nop_entries_keep_their_instruction():
    assert instruction('/bin/sh -c #(nop)  CMD ["bash"]') == 'CMD ["bash"]'
    assert instruction('/bin/sh -c #(nop) ADD file:abc in / ') == 'ADD file:abc in /'


def test_shell_entries_become_run():
    assert instruction('/bin/sh -c apt-get update && apt-get install -y curl') == \
        'RUN apt-get update && apt-get install -y curl'


def test_buildkit_entries_keep_their_instruction_and_lose_the_marker():
    assert instruction('WORKDIR /app # buildkit') == 'WORKDIR /app'
    assert instruction('COPY . . # buildkit') == 'COPY . .'


def test_blank_entries_are_dropped():
    assert instruction('') is None
    assert instruction(None) is None
    assert instruction('   ') is None


def test_unrecognised_entries_become_run():
    assert instruction('apt-get clean') == 'RUN apt-get clean'


def test_from_history_is_oldest_first_and_starts_with_from():
    history = [                                   # the API returns newest first
        {'CreatedBy': '/bin/sh -c #(nop)  CMD ["bash"]'},
        {'CreatedBy': '/bin/sh -c apt-get update'},
        {'CreatedBy': '/bin/sh -c #(nop) ADD file:abc in /'},
    ]
    lines = [l for l in from_history(history).splitlines() if not l.startswith('#')]
    assert lines == [
        'FROM scratch',
        'ADD file:abc in /',
        'RUN apt-get update',
        'CMD ["bash"]',
    ]


def test_from_history_keeps_an_existing_from():
    history = [{'CreatedBy': 'CMD ["sh"] # buildkit'}, {'CreatedBy': 'FROM docker.io/library/alpine'}]
    lines = [l for l in from_history(history).splitlines() if not l.startswith('#')]
    assert lines == ['FROM docker.io/library/alpine', 'CMD ["sh"]']


def test_from_history_says_where_it_came_from():
    text = from_history([{'CreatedBy': 'FROM alpine'}], image_ref='alpine:latest')
    assert text.startswith('# alpine:latest')
    assert 'reconstructed' in text.lower()
    assert text.endswith('\n')


def test_empty_history_still_produces_a_file():
    lines = [l for l in from_history([]).splitlines() if not l.startswith('#')]
    assert lines == ['FROM scratch']


def test_build_arg_prefix_is_stripped_from_run():
    assert instruction('|1 version=1.8.0 /bin/sh -c yum install -y java') == \
        'RUN yum install -y java'
    assert instruction('|2 a=1 b=2 /bin/sh -c make') == 'RUN make'


def test_buildkit_run_loses_its_inner_shell():
    assert instruction('RUN /bin/sh -c apk add git # buildkit') == 'RUN apk add git'


def test_expose_is_rewritten_from_go_map_syntax():
    assert instruction('/bin/sh -c #(nop)  EXPOSE map[9090/tcp:{}]') == 'EXPOSE 9090/tcp'
    assert instruction('/bin/sh -c #(nop)  EXPOSE map[80/tcp:{} 443/tcp:{}]') == \
        'EXPOSE 80/tcp 443/tcp'


def test_exec_form_arrays_get_their_commas_back():
    assert instruction('/bin/sh -c #(nop)  CMD ["java" "-jar" "app.jar"]') == \
        'CMD ["java", "-jar", "app.jar"]'
    assert instruction('/bin/sh -c #(nop)  ENTRYPOINT ["/entrypoint.sh"]') == \
        'ENTRYPOINT ["/entrypoint.sh"]'


def test_a_run_command_with_quotes_is_left_alone():
    assert instruction('/bin/sh -c echo "a" "b" > /tmp/x') == 'RUN echo "a" "b" > /tmp/x'


def test_buildkit_run_with_build_args_is_unwrapped():
    # The shape BuildKit records: RUN, then the build args, then the shell.
    assert instruction('RUN |1 JAR_FILE=app.jar /bin/sh -c chmod +x /entrypoint.sh # buildkit') == \
        'RUN chmod +x /entrypoint.sh'
    assert instruction('RUN |2 a=1 b=2 /bin/sh -c make all') == 'RUN make all'
