.. SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
.. SPDX-License-Identifier: Apache-2.0

{% set constructor = obj.children|selectattr("short_name", "equalto", "__new__")|first %}
{% if constructor is defined and not obj.is_private_member and not obj.constructor %}
{% if obj.display %}
.. py:class:: {{ obj.short_name }}({{ constructor.args }})

   {{ obj.docstring|indent(3) }}

   {{ constructor.docstring|indent(3) }}
{% for child in obj.children|selectattr("display") %}

   {{ child.render()|indent(3) }}
{% endfor %}
{% endif %}
{% else %}
{% include "upstream/python/class.rst" %}
{% endif %}
