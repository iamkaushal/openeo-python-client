from openeo.internal.processes.builder import ProcessBuilderBase, get_parameter_names, convert_callable_to_pgnode


def test_process_builder_process_basic():
    builder = ProcessBuilderBase.process("foo", color="blue")
    assert builder.pgnode.flat_graph() == {
        "foo1": {"process_id": "foo", "arguments": {"color": "blue"}, "result": True}
    }


def test_process_builder_process_namespace():
    builder = ProcessBuilderBase.process("foo", namespace="bar", color="blue")
    assert builder.pgnode.flat_graph() == {
        "foo1": {"process_id": "foo", "namespace": "bar", "arguments": {"color": "blue"}, "result": True}
    }


def test_get_parameter_names():
    def add_stuff(foo, bar, *args, **kwargs):
        return foo + bar + args + kwargs

    assert get_parameter_names(add_stuff) == ["foo", "bar"]
