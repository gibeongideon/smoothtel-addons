LOGICAL_OPERATORS = {"&", "|", "!"}


def _is_domain_leaf(token):
    return (
        isinstance(token, (list, tuple))
        and len(token) >= 3
        and isinstance(token[0], str)
    )


def _is_valid_field_path(env, model_name, field_path):
    if not model_name or not field_path:
        return False
    try:
        model = env[model_name]
    except KeyError:
        return False

    current_model = model
    path_parts = field_path.split(".")
    for index, part in enumerate(path_parts):
        field = current_model._fields.get(part)
        if not field:
            return False
        if index < len(path_parts) - 1:
            comodel_name = getattr(field, "comodel_name", False)
            if not comodel_name:
                return False
            current_model = env[comodel_name]
    return True


def sanitize_domain_for_model(env, model_name, domain):
    removed_paths = []
    tokens = list(domain or [])

    def mark_removed(path):
        if path and path not in removed_paths:
            removed_paths.append(path)

    def make_operator_node(operator, left, right=None):
        if operator == "!":
            return ("not", left) if left else None
        if left and right:
            return ("op", operator, left, right)
        return left or right

    def parse_at(index):
        if index >= len(tokens):
            return None, index

        token = tokens[index]

        if isinstance(token, str) and token in ("&", "|"):
            left, next_index = parse_at(index + 1)
            right, next_index = parse_at(next_index)
            return make_operator_node(token, left, right), next_index

        if token == "!":
            child, next_index = parse_at(index + 1)
            return make_operator_node("!", child), next_index

        if _is_domain_leaf(token):
            field_path = token[0]
            if _is_valid_field_path(env, model_name, field_path):
                return ("leaf", tuple(token)), index + 1
            mark_removed(field_path)
            return None, index + 1

        if isinstance(token, list):
            nested_domain, nested_removed = sanitize_domain_for_model(
                env, model_name, token
            )
            for path in nested_removed:
                mark_removed(path)
            if nested_domain:
                return ("nested", nested_domain), index + 1
            return None, index + 1

        mark_removed(str(token))
        return None, index + 1

    def serialize(node):
        if not node:
            return []
        node_type = node[0]
        if node_type == "leaf":
            return [node[1]]
        if node_type == "nested":
            return node[1]
        if node_type == "not":
            child = serialize(node[1])
            return ["!"] + child if child else []
        if node_type == "op":
            left = serialize(node[2])
            right = serialize(node[3])
            if not left:
                return right
            if not right:
                return left
            return [node[1]] + left + right
        return []

    parsed_nodes = []
    index = 0
    while index < len(tokens):
        node, index = parse_at(index)
        if node:
            parsed_nodes.append(node)

    tree = None
    for node in parsed_nodes:
        tree = node if tree is None else ("op", "&", tree, node)

    return serialize(tree), removed_paths
