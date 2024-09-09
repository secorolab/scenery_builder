# Tutorial on how to Add a Plugin - Example: Adversarial Joint State Plugin

This tutorial assumes that we have already written the plugin itself, and defined a set of parameters that need to be included inside our `.world` file.
We will showcase how to add your plugin to the automatic `.world` file generation using the example of the adversarial joint state plugin. This plugin simply changes the joint state of a door when the robot enters a specified distance to the door.
For the adversarial joint state plugin, an entry into the `.world` file looks as follows:

```xml
<plugin name="adversarial_joint_plugin" filename="libadversarial_joint_plugin.so">
    <joint>JOINT_NAME</joint>
    <x>JOINT_POSITION_BEFORE_TRIGGER</x>
    <near>DISTANCE_TO_TRIGGER</near>
    <y>JOINT_POSITION_AFTER_TRIGGER</y>
</plugin>
```

## Identifying the Static and Dynamic Parameters

When adding a new plugin, you first need to decide which parameters of the plugins we want to be more static (essentially hardcoded values or states that are used across instances of plugins, and that are not easily changed, but can contain very complex information), and which ones we want to keep more dynamic (easy to change, but only very simple values).

For the adversarial joint plugin, the three parameters of importance are `x`, `near` and `y`, since the `joint_name` logically extends from the door instance we are using.

To now decide which of these parameters we want to be static, and which dynamic, I found that its best to actually create an instance of a plugin state, and see how well these parameters fit into our already existing framework:

### Understanding JSON-LD, and Creating a Plugin State File

#### Context

```json
{
    "@context": [
        {
            "pl": "https://secorolab.github.io/metamodels/plugin#",
		    "door": "https://secorolab.github.io/models/door#"
        },
        "https://secorolab.github.io/metamodels/floor-plan/object.json",
        "https://secorolab.github.io/metamodels/floor-plan/plugin.json"
    ],
```

The context of a JSON-LD file defines the namespaces used in the file, and imports information of other JSON-LD files.

In this case the code inside the curly braces defines the namespaces `https://secorolab.github.io/metamodels/plugin#`, abbreviated as `pl`, and `https://secorolab.github.io/models/door#`, abbreviated as `door`.

```json
{
	"pl": "https://secorolab.github.io/metamodels/plugin#",
	"door": "https://secorolab.github.io/models/door#"
}
```

These namespaces are very important, as they connect information inside the current document, with information inside the imported documents, that use the same namespace. It is important to understand that these namespaces **do not necessarily represent actual internet URLs**. The only important thing about them is that they they **exactly** match the namespaces of the imported information.
This information needs to be imported through files hosted either online, or locally using `python3 -m http.server 8000`. In this case, all files are hosted online

```json
"https://secorolab.github.io/metamodels/floor-plan/object.json",
"https://secorolab.github.io/metamodels/floor-plan/plugin.json"
```

The plugin metamodel looks as follows:

```json
{
    "@context": {
        "pl": "https://secorolab.github.io/metamodels/plugin#",
        "Plugin": "pl:Plugin",
        "PluginConfiguration": "pl:PluginConfiguration",
        "plugin-type": {
            "@id": "pl:plugin-type",
            "@type": "PluginConfiguration"
        },
        "uri": {
            "@id": "pl:uri",
            "@type": "PluginConfiguration"
        }
    }
}
```

Here we can see the information imported into our file. It consists of, again, our namespace `"pl": "https://secorolab.github.io/metamodels/plugin#"` and then several other defined concepts contained inside the metamodel, many of which will become relevant later on.

#### Graph

Now that we have defined the context of our file, we will define the potential instances of our plugin that act as nodes in our graph. At first this will look as follows for all plugins you may add:

```json
"@graph": [
        {
            "@id": "pl:placeholder-adversarial-plugin-id",
            "@type": "PluginConfiguration",
            "plugin-type": "adversarial",
        }
    ]
```

- `"@id": "pl:placeholder-adversarial-plugin-id"`, defines the ID that we will use to assign this specific instance of the adversarial plugin to a door instance.
- `"@type": "PluginConfiguration"` may be used at some point in our code to ensure that the information entered into the graph is the correct type, since JSON-LD does not have any form of type checking.
- `"plugin-type": "adversarial"` will be used later in our python code to identify which plugin is currently being parsed.

#### Adding Our Parameters

To reiterate, we identified three different important parameters for our plugin:

- `x`: the joint position before the trigger
- `near`: the distance at which the plugin triggers in meter
- `y`: the joint position after the trigger

If we look at existing models and metamodels in our repositories, we will notice that the we already have several different door states defined here, as well as, more importantly, *transitions*, from one state to another. Both the `state` of the doors, and the `transition` between these states, are types defined inside the state metamodel, which can be imported using `"https://secorolab.github.io/metamodels/floor-plan/state.json"`, and the actual definition of the state or transition is defined inside the `object-door-states.json` (update as soon as we decided where object-door-states should be located). Since we literally need a transition between `x` and `y`, it makes sense to add another field `transition` to our instance, and since we have six different transitions defined inside `object-door-states.json`, we will now define six different instances of our adversarial joint plugin, each with a unique `id`:

```json
"@graph": [
        {
            "@id": "pl:door-opened-to-closed-adversarial-plugin",
            "@type": "PluginConfiguration",
            "plugin-type": "adversarial",
            "transition": "door:transition-from-door-fully-opened-to-door-fully-closed"
        },
        {
            "@id": "pl:door-closed-to-opened-adversarial-plugin",
            "@type": "PluginConfiguration",
            "plugin-type": "adversarial",
            "transition": "door:transition-from-door-fully-closed-to-door-fully-opened"
        },
        {
            "@id": "pl:door-closed-to-partially-adversarial-plugin",
            "@type": "PluginConfiguration",
            "plugin-type": "adversarial",
            "transition": "door:transition-from-door-fully-closed-to-door-partially-opened"
        },
        {
            "@id": "pl:door-partially-to-closed-adversarial-plugin",
            "@type": "PluginConfiguration",
            "plugin-type": "adversarial",
            "transition": "door:transition-from-door-partially-opened-to-door-fully-closed"
        },
        {
            "@id": "pl:door-partially-to-opened-adversarial-plugin",
            "@type": "PluginConfiguration",
            "plugin-type": "adversarial",
            "transition": "door:transition-from-door-partially-opened-to-door-fully-opened"
        },
        {
            "@id": "pl:door-opened-to-partially-adversarial-plugin",
            "@type": "PluginConfiguration",
            "plugin-type": "adversarial",
            "transition": "door:transition-from-door-fully-opened-to-door-partially-opened"
        }
    ]
```

From that `transition`, we will later be able to extract the positions for `x` and `y`.
Now we need to define `near`. Now we have two options for what to do. Either we create another field `near` (or `distance`, as it is more descriptive) or we define the parameter when we add the plugin to our door instance.
Since we preferably want all permutations of combinations, as a individual instance, just having z=3 different values, for example 1m, 0.5m, 0,25m, would mean that we end up with 6\*z=18 different instances, which all need to have unique names, which will consequently either get increasingly long, or increasingly less descriptive.
A better way to do it instead, is to define the `distance` parameter inside our door instance instead.

## Adding the Plugins to a Door Instance

After locating the file of door-instance-1 in our model folder, we need to find an entry already adding an instance of the `initial-state-plugin` (since every door-instance must have an instance of the `initial-state-plugin`):

```json
{
	"@id": "door:door-instance-1",
	"@type": "ObjectInstance",
	"frame": "geom:frame-location-door-1",
	"of-object": "door:door",
	"world": "floorplan:frontiers_brsu_building_c",
	"plugins": [
		{
			"@id": "pl:door-partially-opened-init-plugin"
		}
	]
}
```

Now to add a instance of our new plugin (for example `pl:door-opened-to-closed-adversarial-plugin`) to this door instance, and also set the `distance` parameter, we first need to add it to our `plugin.json` metamodel, which should now look as follows:

```json
{
    "@context": {
        "pl": "https://secorolab.github.io/metamodels/plugin#",
        "Plugin": "pl:Plugin",
        "PluginConfiguration": "pl:PluginConfiguration",
        "plugin-type": {
            "@id": "pl:plugin-type",
            "@type": "PluginConfiguration"
        },
        "uri": {
            "@id": "pl:uri",
            "@type": "PluginConfiguration"
        },
        "distance": {
            "@id": "pl:distance",
            "@type": "PluginConfiguration"
        },
    }
}
```

Then we need to edit the code of our door instance code as follows:

```json
{
	"@id": "door:door-instance-1",
	"@type": "ObjectInstance",
	"frame": "geom:frame-location-door-1",
	"of-object": "door:door",
	"world": "floorplan:frontiers_brsu_building_c",
	"plugins": [
		{
			"@id": "pl:door-partially-opened-init-plugin"
		},
		{
			"@id": "pl:door-opened-to-closed-adversarial-plugin",
			"distance": "0.9"
		}
	]
}
```

## Parsing the Plugin inside the Scenery Builder

Inside the `scenery_builder` repository, inside the method `get_object_instance` of the file `src/fpm/transformations/objects.py`, is where the parsing of the plugins happens. In line 172, we find the following `If` statements:

```Python
if plugin_type == "initial":  
    state = g.value(plugin, ST["state"])  
    start_value = get_joint_state_value(state)  
  
    if not start_value:  
        raise ValueError("Initial plugin must have a start value")  
  
    plugins.append({  
        "plugin_type": plugin_type,  
        "joint": joint_name,  
        "position": start_value  
    })  
  
  
elif plugin_type == "dynamic":  
    uri = g.value(plugin, PL["uri"])  
    plugins.append({  
        "plugin_type": plugin_type,  
        "joint": joint_name,  
        "uri": uri  
    })  
```

Here we now add another case for `plugin_type == "adversarial"`. First thing we will do is extract the value of the `transition` field, and from here, extract the `start_value`, which will be our `x`, and the `end_value`, which will be our `y`. Afterwards we will extract the value of the `distance` field which will be our `near`.
Lastly we will append this information, as well as the `joint` and the `plugin_type`, which will have been extracted earlier, to our `plugins` list.

```Python
elif plugin_type == "adversarial":  
    transition = g.value(plugin, ST["transition"])  
    start_value = get_joint_state_value(g.value(transition, ST["start-state"]))  
    end_value = get_joint_state_value(g.value(transition, ST["end-state"]))  
    distance = float(g.value(plugin, PL["distance"]))  
    plugins.append({  
        "plugin_type": plugin_type,  
        "joint": joint_name,  
        "position_before": start_value,  
        "distance_to_trigger": distance,  
        "position_after": end_value  
    })
```

One last tip:
Dealing with `g.value()` calls can be quite tricky. What helped me a lot is using the following loop, to query the current graph and find out which parameters I need to query, or spot instances where I maybe made a mistake inside the JSON-LD files:

```Python
for subj, pred, obj in g:
	if subj == plugin:  
	    print(f"Subject: {subj}, Predicate: {pred}, Object: {obj}")
```

In this loop, you can swap out the subject, predicate and object depending on your query, and swap our plugin with the value that subject/predicate/object you are interested in.

## Adding the New Plugin to the Jinja Template

The `world.sdf.jinja` file can be found inside the `scenery_builder`, at `src/fpm/templates/gazebo/world.sdf.jinja`. In Line 34 you should find the following code block:

```xml
{%- for plugin_config in instance.plugin_configs %}  
    {%- if plugin_config.plugin_type == 'initial' %}  
	<plugin name="initial_plugin" filename="libinitial_plugin.so">  
	    <joint>{{plugin_config.joint}}</joint>  
	    <position>{{plugin_config.position}}</position>  
	</plugin>    
	{%- elif plugin_config.plugin_type == 'dynamic' %}  
	<plugin name="dynamic_joint_pluginss" filename="libdynamic_joint_plugin.so">  
	    <joint>{{plugin_config.joint}}</joint>  
	    <uri>{{plugin_config.uri}}</uri>  
	</plugin>    
	{%- endif %}  
{%- endfor %}
```

To now add our new plugin, we need to add another `elif` statement, and then extract the values using the keywords we have previously defined inside the dictionary we appended to the `plugin` list:

```xml
{%- elif plugin_config.plugin_type == 'adversarial' %}  
<plugin name="adversarial_joint_plugin" filename="libadversarial_joint_plugin.so">  
	<joint>{{plugin_config.joint}}</joint>  
	<x>{{plugin_config.position_before}}</x>  
	<near>{{plugin_config.distance_to_trigger}}</near>  
	<y>{{plugin_config.position_after}}</y>  
</plugin>
```

## Design Decisions and Examples

Currently, continuing with the same design choices made for the door states, our plugin states JSON-LD files multiple unique instances of the same plugin, with each instance representing a unique plugin configuration. Each unique configuration should be easily identifiable by its ID, to make it easy to use. For example:

- `"pl:door-partially-to-closed-adversarial-plugin"` is the adversarial door plugin with a configuration that has a partially-opened door state (0.7) as the start state, and the closed door state (0.0) as the end state.
- `"pl:door-opened-to-closed-adversarial-plugin"` is the adversarial door plugin with a configuration that has a fully-opened door state (1.6) as the start state, and the closed door state (0.0) as the end state.
- `"pl:door-opened-to-partially-adversarial-plugin"` is the adversarial door plugin with a configuration that has a fully-opened door state (1.6) as the start state, and the partially-opened door state (0.7) as the end state.

While we may use the same plugin ID for multiple door instances, each instance is assigned its own plugin using the jinja template. This is also evidenced by the fact, that some plugins, like the adversarial door plugin, have dynamic parameters like the `distance` parameter, that may be totally unique for each door instance.
Adding the following to door-instance-1:

```xml
{
"@id": "pl:door-opened-to-closed-adversarial-plugin",
"distance": "0.9"
},
```

Will result in this plugin being generated:

```xml
<plugin name="adversarial_joint_plugin" filename="libadversarial_joint_plugin.so">
  <joint>door:door-instance-1-hinge-joint</joint>
  <x>1.6</x>
  <near>0.9</near>
  <y>0.0</y>
</plugin>
```

And adding the following to door-instance-2, using a different value for “distance”, but otherwise the same plugin configuration:

```xml
{
"@id": "pl:door-opened-to-closed-adversarial-plugin",
"distance": "0.3"
},
```

Will result in this plugin being generated:

```xml
<plugin name="adversarial_joint_plugin" filename="libadversarial_joint_plugin.so">
  <joint>door:door-instance-2-hinge-joint</joint>
  <x>1.6</x>
  <near>0.3</near>
  <y>0.0</y>
</plugin>
```

Using this method, we make sure to have as little duplicated code as possible, since we clearly define the most common plugin states, while still maintaining some flexibility by being able to assign dynamic parameters like the `distance` parameter, and while still making sure the plugins are easy to use.
This still comes with some tradeoffs. We need to carefully choose the static parameters, since too many too many instances of the static parameters will result in a lot of unique plugin config permutations. For example we have three predefined door states, (opened, partially, closed), and this already resulted in 6 unique transitions.

If it turns out that we need unique IDs for each plugin, I would recommend generating the ID inside the python code and then inserting it into the jinja template, similar to how i currently generate the joint-name of each instance:

```Python
joint_name = f"{prefixed(g, instance)}-hinge-joint"
```

Using this, the joint-name of door-instance-1 would be `door:door-instance-1-hinge-joint`.
