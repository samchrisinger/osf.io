## Knockout templates for OSF-core (non-addon) logs. Used by logFeed.js to render the log feed
## the id attribute of each script tag corresponds to NodeLog action.
## When the application is initialized, this mako template is concatenated with the addons'
## log templates. An addon's log templates are located in
## website/addons/<addon_name>/templates/log_templates.mako.

## Embargo related logs
<script type="text/html" id="embargo_approved">
approved embargoed registration of
<a class="log-node-title-link overflow" data-bind="text: nodeTitle, attr: {href: nodeUrl}"></a>
</script>

<script type="text/html" id="embargo_approved_no_user">
Embargo for
<a class="log-node-title-link overflow" data-bind="text: nodeTitle, attr: {href: nodeUrl}"></a> approved
</script>

<script type="text/html" id="embargo_cancelled">
cancelled embargoed registration of
<span class="log-node-title-link overflow" data-bind="text: nodeTitle"></span>
</script>

<script type="text/html" id="embargo_completed">
completed embargo of
<a class="log-node-title-link overflow" data-bind="text: nodeTitle, attr: {href: nodeUrl}"></a>
</script>

<script type="text/html" id="embargo_completed_no_user">
Embargo for
<a class="log-node-title-link overflow" data-bind="text: nodeTitle, attr: {href: nodeUrl}"></a> completed
</script>

<script type="text/html" id="embargo_initiated">
initiated an embargoed registration of
<!-- ko if: !registrationCancelled -->
<a class="log-node-title-link overflow" data-bind="text: nodeTitle, attr: {href: nodeUrl}"></a>
<!-- /ko -->

<!-- ko if: registrationCancelled -->
<span class="log-node-title-link overflow" data-bind="text: nodeTitle"></span>
<!-- /ko -->
</script>

<script type="text/html" id="embargo_terminated_no_user">
Embargo for
<a class="log-node-title-link overflow" data-bind="text: nodeTitle, attr: {href: nodeUrl}"></a>
ended.
</script>

## Retraction related logs
<script type="text/html" id="retraction_approved">
approved withdrawal of registration of
<a class="log-node-title-link overflow" data-bind="text: nodeTitle, attr: {href: nodeUrl}"></a>
</script>

<script type="text/html" id="retraction_cancelled">
cancelled withdrawal of registration of
<span class="log-node-title-link overflow" data-bind="text: nodeTitle"></span>
</script>

<script type="text/html" id="retraction_initiated">
initiated withdrawal of registration of
<a class="log-node-title-link overflow" data-bind="text: nodeTitle, attr: {href: nodeUrl}"></a>
</script>

## Registration related Logs
<script type="text/html" id="registration_initiated">
initiated registration of
<!-- ko if: !registrationCancelled -->
<a class="log-node-title-link overflow" data-bind="text: nodeTitle, attr: {href: nodeUrl}"></a>
<!-- /ko -->

<!-- ko if: registrationCancelled -->
<span class="log-node-title-link overflow" data-bind="text: nodeTitle"></span>
<!-- /ko -->
</script>

<script type="text/html" id="registration_cancelled">
cancelled registration of
<span class="log-node-title-link overflow" data-bind="text: nodeTitle"></span>
</script>

<script type="text/html" id="registration_approved">
approved registration of
<a class="log-node-title-link overflow" data-bind="text: nodeTitle , attr: {href: nodeUrl}"></a>
</script>

<script type="text/html" id="registration_approved_no_user">
Registration of
<a class="log-node-title-link overflow" data-bind="text: nodeTitle, attr: {href: nodeUrl}"></a> approved
</script>

## Project related logs
<script type="text/html" id="project_created">
created
<a class="log-node-title-link overflow" data-bind="text: nodeTitle, attr: {href: nodeUrl}"></a>
</script>

<script type="text/html" id="project_deleted">
deleted
<span class="log-node-title-link overflow" data-bind="text: nodeTitle"></span>
</script>

<script type="text/html" id="created_from">
created
<a class="log-node-title-link overflow" data-bind="text: nodeTitle, attr: {href: nodeUrl}"></a>
based on <a class="log-node-title-link overflow"
data-bind="text: params.template_node.title || 'another', attr: {href: params.template_node.url}"></a>
</script>

<script type="text/html" id="node_created">
created
<a class="log-node-title-link overflow" data-bind="text: nodeTitle, attr: {href: nodeUrl}"></a>
</script>

<script type="text/html" id="node_removed">
removed
<span class="log-node-title-link overflow" data-bind="text: nodeTitle"></span>
</script>

<script type="text/html" id="contributor_added">
added
<span data-bind="html: displayContributors"></span>
as contributor(s) to
<a class="log-node-title-link overflow" data-bind="attr: {href: $parent.nodeUrl}, text: $parent.nodeTitle"></a>
</script>

<script type="text/html" id="contributor_removed">
removed
<span data-bind="html: displayContributors"></span>
as contributor(s) from
<a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}, text: nodeTitle"></a>
</script>

<script type="text/html" id="contributors_reordered">
reordered contributors for
<a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}, text: nodeTitle"></a>
</script>

<script type="text/html" id="checked_in">
checked in <span data-bind="text: params.kind"></span>
<a class="overflow log-file-link" data-bind="click: NodeActions.addonFileRedirect, text: stripSlash(params.path)"></a>
from <a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}, text: nodeTitle"></a>
</script>

<script type="text/html" id="checked_out">
checked out <span data-bind="text: params.kind"></span>
<a class="overflow log-file-link" data-bind="click: NodeActions.addonFileRedirect, text: stripSlash(params.path)"></a>
from
<a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}, text: nodeTitle"></a>
</script>

<script type="text/html" id="permissions_updated">
changed permissions for
<a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}, text: nodeTitle"></a>
</script>

<script type="text/html" id="made_public">
made
<a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}, text: nodeTitle"></a> public
</script>

<script type="text/html" id="made_public_no_user">
    <a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}, text: nodeTitle"></a> made public
</script>

<script type="text/html" id="made_private">
made
<a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}, text: nodeTitle"></a> private
</script>

<script type="text/html" id="tag_added">
tagged
<a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}, text: nodeTitle"></a> as <a data-bind="attr: {href: '/search/?q=%22' + params.tag + '%22'}, text: params.tag"></a>
</script>

<script type="text/html" id="tag_removed">
removed tag <a data-bind="attr: {href: '/search/?q=%22' + params.tag + '%22'}, text: params.tag"></a>
from
<a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}, text: nodeTitle"></a>
</script>

<script type="text/html" id="file_tag_added">
tagged <a class="overflow log-file-link" data-bind="click: NodeActions.addonFileRedirect, text: stripSlash(params.path)"></a>
in <a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}, text: nodeTitle"></a>
as <a data-bind="attr: {href: '/search/?q=%22' + params.tag + '%22'}, text: params.tag"></a>
in OSF Storage
</script>

<script type="text/html" id="file_tag_removed">
removed tag <a data-bind="attr: {href: '/search/?q=%22' + params.tag + '%22'}, text: params.tag"></a>
from <a class="overflow log-file-link" data-bind="click: NodeActions.addonFileRedirect, text: stripSlash(params.path)"></a>
in <a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}, text: nodeTitle"></a>
in OSF Storage
</script>

<script type="text/html" id="edit_title">
changed the title from <span class="overflow" data-bind="text: params.title_original"></span>
to
<a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}, text: params.title_new"></a>
</script>

<script type="text/html" id="project_registered">
   <!-- ko if: params.is_prereg -->
        initiated registration of
        <a class="log-node-title-link overflow" data-bind="text: nodeTitle, attr: {href: projectUrl}"></a>.
        It was submitted for review to the Preregistration Challenge on
    <!-- /ko -->
    <!-- ko ifnot: params.is_prereg -->
        registered
        <a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}, text: nodeTitle"></a>
    <!-- /ko -->
</script>

<script type="text/html" id="project_registered_no_user">
<a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}, text: nodeTitle"></a> registered
</script>

<script type="text/html" id="node_forked">
created fork from
<a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}, text: nodeTitle"></a>
</script>

<script type="text/html" id="edit_description">
edited description of  <a class="log-node-title-link" data-bind="attr: {href: nodeUrl}, text: nodeTitle"></a>
</script>

<script type="text/html" id="license_changed">
updated the license of <a class="log-node-title-link" data-bind="attr: {href: nodeUrl}, text: nodeTitle"></a>
</script>

<script type="text/html" id="updated_fields">
  changed the <span data-bind="listing: {
                                 data: params.updated_fields,
                                 map: mapUpdates
                               }"></span> for
  <a class="log-node-title-link" data-bind="attr: {href: nodeUrl}, text: nodeTitle"></a>
</script>

<script type="text/html" id="pointer_created">
created a link to <span data-bind="text: params.pointer.category"></span>
<a class="log-node-title-link overflow" data-bind="text: params.pointer.title, attr: {href: params.pointer.url}"></a>
</script>

<script type="text/html" id="pointer_removed">
removed a link to <span data-bind="text: params.pointer.category"></span>
<a class="log-node-title-link overflow" data-bind="text: params.pointer.title, attr: {href: params.pointer.url}"></a>
</script>

<script type="text/html" id="pointer_forked">
forked a link to <span data-bind="text: params.pointer.category"></span>
<a class="log-node-title-link overflow" data-bind="text: params.pointer.title, attr: {href: params.pointer.url}"></a>
</script>

<script type="text/html" id="addon_added">
added addon <span data-bind="text: params.addon"></span>
to
<a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}, text: nodeTitle"></a>
</script>

<script type="text/html" id="addon_removed">
removed addon <span data-bind="text: params.addon"></span>
from
<a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}, text: nodeTitle"></a>
</script>

<script type="text/html" id="comment_added">
added a comment
to
<!-- ko if: params.file -->
<a data-bind="attr: {href: params.file.url}, text: params.file.name"></a>
in
<!-- /ko -->
<!-- ko if: params.wiki -->
wiki page
<a data-bind="attr: {href: params.wiki.url}, text: params.wiki.name"></a>
in
<!-- /ko -->
<a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}, text: nodeTitle"></a>
</script>

<script type="text/html" id="comment_updated">
updated a comment
on
<!-- ko if: params.file -->
<a data-bind="attr: {href: params.file.url}, text: params.file.name"></a>
in
<!-- /ko -->
<!-- ko: params.wiki -->
wiki page
<a data-bind="attr: {href: params.wiki.url}, text: params.wiki.name"></a>
in
<!-- /ko -->
<a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}, text: nodeTitle"></a>
</script>

<script type="text/html" id="comment_removed">
deleted a comment
on
<!-- ko if: params.file -->
<a data-bind="attr: {href: params.file.url}, text: params.file.name"></a>
in
<!-- /ko -->
<!-- ko if: params.wiki -->
wiki page
<a data-bind="attr: {href: params.wiki.url}, text: params.wiki.name"></a>
in
<!-- /ko -->
<a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}, text: nodeTitle"></a>
</script>

<script type="text/html" id="comment_restored">
restored a comment
on
<!-- ko if: params.file -->
<a data-bind="attr: {href: params.file.url}, text: params.file.name"></a>
in
<!-- /ko -->
<!-- ko if: params.wiki -->
wiki page
<a data-bind="attr: {href: params.wiki.url}, text: params.wiki.name"></a>
in
<!-- /ko -->
<a class="log-node-title-link overflow" data-bind="attr: {href: nodeUrl}, text: nodeTitle"></a>
</script>

<script type="text/html" id="made_contributor_visible">
    <!-- ko if: log.anonymous -->
        changed a non-bibliographic contributor to a bibliographic contributor on
    <!-- /ko -->
    <!-- ko ifnot: log.anonymous -->
        made non-bibliographic contributor
        <span data-bind="html: displayContributors"></span>
        a bibliographic contributor on
    <!-- /ko -->
    <a class="log-node-title-link overflow" data-bind="attr: {href: $parent.nodeUrl}, text: $parent.nodeTitle"></a>
</script>

<script type="text/html" id="made_contributor_invisible">
    <!-- ko if: log.anonymous -->
        changed a bibliographic contributor to a non-bibliographic contributor on
    <!-- /ko -->
    <!-- ko ifnot: log.anonymous -->
        made bibliographic contributor
        <span data-bind="html: displayContributors"></span>
        a non-bibliographic contributor on
    <!-- /ko -->
    <a class="log-node-title-link overflow" data-bind="attr: {href: $parent.nodeUrl}, text: $parent.nodeTitle"></a>
</script>

<script type="text/html" id="addon_file_copied">
  <!-- ko if: params.source.materialized.endsWith('/') -->
    copied <span class="overflow log-folder" data-bind="text: params.source.materialized"></span> from <span data-bind="text: params.source.addon"></span> in
    <a class="log-node-title-link overflow" data-bind="attr: {href: params.source.node.url}, text:params.source.node.title"></a>
    to <span class="overflow log-folder" data-bind="text: params.destination.materialized"></span> in <span data-bind="text: params.destination.addon"></span> in
    <a class="log-node-title-link overflow" data-bind="attr: {href: $parent.nodeUrl}, text: $parent.nodeTitle"></a>
  <!-- /ko -->
  <!-- ko ifnot: params.source.materialized.endsWith('/') -->
    copied <a data-bind="attr: {href: params.source.url}, text: params.source.materialized" class="overflow"></a> from <span data-bind="text: params.source.addon"></span> in
    <a class="log-node-title-link overflow" data-bind="attr: {href: params.source.node.url}, text: params.source.node.title"></a>
    to <a data-bind="attr: {href: params.destination.url}, text: params.destination.materialized" class="overflow"></a> in <span data-bind="text: params.destination.addon"></span> in
    <a class="log-node-title-link overflow" data-bind="attr: {href: $parent.nodeUrl}, text: $parent.nodeTitle"></a>
  <!-- /ko -->
</script>

<script type="text/html" id="addon_file_moved">
  <!-- ko if: params.source.materialized.endsWith('/') -->
  moved <span class="overflow" data-bind="text: params.source.materialized"></span> from <span data-bind="text: params.source.addon"></span> in
  <a class="log-node-title-link overflow" data-bind="attr: {href: params.source.node.url}, text: params.source.node.title"></a>
  to <span class="overflow log-folder" data-bind="text: params.destination.materialized"></span> in <span data-bind="text: params.destination.addon"></span> in
  <a class="log-node-title-link overflow" data-bind="attr: {href: $parent.nodeUrl}, text: $parent.nodeTitle"></a>
  <!-- /ko -->
  <!-- ko ifnot: params.source.materialized.endsWith('/') -->
  moved <span class="overflow" data-bind="text: params.source.materialized"></span> from <span data-bind="text: params.source.addon"></span> in
  <a class="log-node-title-link overflow" data-bind="attr: {href: params.source.node.url}, text: params.source.node.title"></a>
  to <a class="overflow" data-bind="attr: {href: params.destination.url}, text: params.destination.materialized"></a> in <span data-bind="text: params.destination.addon"></span> in
  <a class="log-node-title-link overflow" data-bind="attr: {href: $parent.nodeUrl}, text: $parent.nodeTitle"></a>
  <!-- /ko -->
</script>

<script type="text/html" id="addon_file_renamed">
    renamed <span class="overflow" data-bind="text: params.source.materialized"></span>
  <!-- ko if: params.source.materialized.endsWith('/') -->
  to <span class="overflow log-folder" data-bind="text: params.destination.materialized"></span> in <span data-bind="text: params.destination.addon"></span> in
  <!-- /ko -->
  <!-- ko ifnot: params.source.materialized.endsWith('/') -->
  to <a class="overflow" data-bind="attr: {href: params.destination.url}, text: params.destination.materialized"></a> in <span data-bind="text: params.destination.addon"></span>  in
  <!-- /ko -->
    <a class="log-node-title-link overflow" data-bind="attr: {href: $parent.nodeUrl}, text: $parent.nodeTitle"></a>
</script>

<script type="text/html" id="external_ids_added">
created external identifiers
<span data-bind="text: 'doi:' + params.identifiers.doi"></span> and
<span data-bind="text: 'ark:' + params.identifiers.ark"></span>
on
<a class="log-node-title-link overflow" data-bind="attr: {href: $parent.nodeUrl}, text: $parent.nodeTitle"></a>
</script>

<script type="text/html" id="citation_added">
added a citation (<span data-bind="text: params.citation.name"></span>)
to
<a class="log-node-title-link overflow" data-bind="attr: {href: $parent.nodeUrl}, text: $parent.nodeTitle"></a>
</script>

<script type="text/html" id="citation_edited">
<!-- ko if: params.citation.new_name -->
updated a citation name from <span data-bind="text: params.citation.name"></span> to <strong data-bind="text: params.citation.new_name"></strong>
  <!-- ko if: params.citation.new_text -->
    and edited its text
  <!-- /ko -->
<!-- /ko -->
<!-- ko ifnot: params.citation.new_name -->
edited the text of a citation (<span data-bind="text: params.citation.name"></span>)
<!-- /ko -->
on
<a class="log-node-title-link overflow" data-bind="attr: {href: $parent.nodeUrl}, text: $parent.nodeTitle"></a>
</script>

<script type="text/html" id="citation_removed">
removed a citation (<span data-bind="text: params.citation.name"></span>)
from
<a class="log-node-title-link overflow" data-bind="attr: {href: $parent.nodeUrl}, text: $parent.nodeTitle"></a>
</script>

<script type="text/html" id="primary_institution_changed">
changed primary institution of <a class="log-node-title-link overflow" data-bind="text: nodeTitle, attr: {href: nodeUrl}"></a>
<!-- ko if: params.previous_institution.name != 'None' --><!-- TODO: Check datatypes here -->
 from <a class="log-node-title-link overflow" data-bind="attr: {href: '/institutions/' + params.previous_institution.id}, text: params.previous_institution.name"></a>
<!-- /ko -->
 to <a class="log-node-title-link overflow" data-bind="attr: {href: '/institutions/' + params.institution.id}, text: params.institution.name"></a>.
</script>

<script type="text/html" id="primary_institution_removed">
removed <a class="log-node-title-link overflow" data-bind="attr: {href: '/institutions/' + params.institution.id}, text: params.institution.name"></a>
as the primary institution of <a class="log-node-title-link overflow" data-bind="text: nodeTitle, attr: {href: nodeUrl}"></a>.
</script>
