<script type="text/html" id="dataverse_file_added">
added file
<a class="overflow log-file-link" data-bind="click: NodeActions.addonFileRedirect, text: params.filename"></a> to
Dataverse dataset <span class="overflow">{{ params.dataset }}</span>
in {{ nodeType }}
<a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}">{{ nodeTitle }}</a>
</script>

<script type="text/html" id="dataverse_file_removed">
removed file <span class="overflow">{{ params.filename }}</span> from
Dataverse dataset <span class="overflow">{{ params.dataset }}</span>
in {{ nodeType }}
<a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}">{{ nodeTitle }}</a>
</script>

<script type="text/html" id="dataverse_dataset_linked">
linked Dataverse dataset
<span class="overflow">{{ params.dataset }}</span> to {{ nodeType }}
<a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}">{{ nodeTitle }}</a>
</script>

<!-- Legacy version -->
<script type="text/html" id="dataverse_study_linked">
linked Dataverse dataset
<span class="overflow">{{ params.study }}</span> to {{ nodeType }}
<a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}">{{ nodeTitle }}</a>
</script>

<script type="text/html" id="dataverse_dataset_published">
published a new version of Dataverse dataset
<span class="overflow">{{ params.dataset }}</span> to {{ nodeType }}
for {{ nodeType }}
<a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}">{{ nodeTitle }}</a>
</script>

<!-- Legacy version -->
<script type="text/html" id="dataverse_study_released">
published a new version of Dataverse dataset
<span class="overflow">{{ params.study }}</span> to {{ nodeType }}
for {{ nodeType }}
<a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}">{{ nodeTitle }}</a>
</script>

<script type="text/html" id="dataverse_node_authorized">
authorized the Dataverse addon for {{ nodeType }}
<a class="log-node-title-link overflow"
    data-bind="attr: {href: nodeUrl}">{{ nodeTitle }}</a>
</script>

<script type="text/html" id="dataverse_node_deauthorized">
deauthorized the Dataverse addon for {{ nodeType }}
<a class="log-node-title-link overflow"
    data-bind="attr: {href: nodeUrl}">{{ nodeTitle }}</a>
</script>
