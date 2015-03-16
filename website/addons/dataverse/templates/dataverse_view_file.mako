<%inherit file="project/addon/view_file.mako" />

<%def name="title()">${file_name}</%def>

<%def name="file_versions()">
<div class="scripted" id="dataverseScope">

    <ol class="breadcrumb">
         <li class="active overflow"><a data-bind="attr: {href: files_url}">{{nodeTitle}}</a></li>
         <li>Dataverse</li>
         <li class="active overflow">{{filename}}</li>
    </ol>

     <p>
         <a data-bind="attr: {href: download_url}" class="btn btn-success btn-md">Download <i class="fa fa-download"></i></a>
         ## TODO: Disable based on whether file is draft version. Re-evaluate on release of Dataverse 4.0
##        % if user['can_edit']:
##            <button data-bind="click: deleteFile" class="btn btn-danger btn-md">Delete <i class="fa-trash-o"></i></button>
##        % endif
     </p>


    % if not node['anonymous']:
            <table class="table table-striped" id="file-version-history">
                <thead>
                <tr>
                    <th>Dataverse</th>
                    <th>Study</th>
                    <th>Download</th>
                </tr>
                </thead>

                <tbody>
                    <tr data-bind="if: loaded">
                        <td>
                            <a data-bind="attr: {href: dataverse_url}">
                                {{dataverse}}</a>
                        </td>
                        <td>
                            <a data-bind="attr: {href: study_url}">
                                {{study}}</a>
                        </td>
                        <td>
                            <a data-bind="attr: {href: download_url}" class="btn btn-primary btn-sm">
                                <i class="fa fa-download"></i>
                            </a>
                        </td>
                    </tr>
                </tbody>

            </table>

    % endif
</div>
    <script type="text/javascript">
        window.contextVars = $.extend(true, {}, window.contextVars, {
            node: {
                urls: {
                    info: '${urls['info']}'
                    }
            }
        });
    </script>
</%def>

<%def name="javascript_bottom()">
${parent.javascript_bottom()}
<script src=${"/static/public/js/dataverse/file-detail.js" | webpack_asset}></script>
</%def>
