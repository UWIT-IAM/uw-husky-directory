# Jinja Templates

## Custom Filters

### `titleize`

```
'foo_bar' == becomes ==> 'Foo Bar'
'fooBar' == becomes ==> 'Foo Bar'
```

### `singularize`

```
'foos' == becomes ==> 'foo'
'faculty' == becomes ==> 'faculty'
```

### linkify

```
'foo bar baz' == becomes ==> 'foo-bar-baz'
```

### externalize

We present the "employee" population as "faculty/staff;" this filter
can be used to register other strings that, when encountered, should be 
presented another way.

```
'employees' == becomes ==> 'faculty/staff'
'something else' == becomes ==> 'something else'
```

## Custom predicates

### `blank`

Returns `True` if value is either undefined _or_ set to `None`.



## Helpful Hints

### Whitespace Control

To control whitespace in jinja templates, you have to undersatnd it. 

If you type:

```
{% for foo in bar %}
    (
    {{ foo }}
    )\n
{% endfor %}
```

Jinja sees:

```
{% for foo in bar %}\n
    (\n
    {{ foo }}\n
    )\n
{% endfor %}\n
```

Jinja will not assume you want those newlines trimmed. 
To trim them, you have to use the `-` modifier.

In `{% for foo in bar %}\n`, we can strip `\n` by using `-%}`, which means 
"strip the newline you're about to encounter." 

So: Use `-%}` or `-}}` to indicate you want jinja to ignore the _next_
newline that is encountered.

Use `{%-` or `{{-` to ignore the _previous_ newline that was encountered.

In the above example, with `bar=[1,2,3,4]` we could:

#### Render each block on its own line

```
{% for foo in bar -%}
    (
    {{- foo -}}
    )
{%- endfor %}\n
```

looks to Jinja like:


```
{% for foo in bar -%}
    (
    {{- foo -}}
    )
{%- endfor %}\n
```

So the result is:

```
(1)
(2)
(3)
(4)
```

#### Render the whole block on a single line:

Same as above, but we remove the last newline as well:

```
{% for foo in bar -%}
(
{{- foo -}}
)
{%- endfor -%}
```

has no newlines (unless there was a newline prior to this block) 
so the output would render as:

```
(1)(2)(3)(4)
```
