<%page args="scripted" />

### Included where the LogsViewModel is used ###
<div id="logProgressBar" class="progress progress-striped active">
    <div class="progress-bar"  role="progressbar" aria-valuenow="100" aria-valuemin="0" aria-valuemax="100" style="width: 100%">
        <span class="sr-only">Loading</span>
    </div>
</div>

<div
    %if scripted:
        class="scripted"
    %endif
        id="logScope">

    <div class="logs addon-widget-container">

        <div class="components">
            <div class="addon-widget-header clearfix"> 
                <h4>Recent Activity </h4>
                <div class="pull-right">
                </div>
            </div>
            <div class="addon-widget-body">
                <p class="help-block" data-bind="if: tzname">
                    All times displayed at
                    <span data-bind="text: tzname"></span>
                    <a href="http://en.wikipedia.org/wiki/Coordinated_Universal_Time" target="_blank">UTC</a> offset.
                </p>

                <p data-bind="if: !logs().length" class="help-block">
                    No logs to show. Click the watch icon (<i class="fa fa-eye"></i>) icon on a
                    project's page to get activity updates here.
                </p>

                <dl class="dl-horizontal activity-log" data-bind="foreach: {data: logs, as: 'log'}">
                    <dt><span class="date log-date" data-bind="text: log.date.local, tooltip: {title: log.date.utc}"></span></dt>
                    <dd class="log-content break-word">

                        <!-- ko if: log.hasTemplate() -->
                        <span data-bind="if:log.anonymous">
                        <span class="contributor-anonymous">A user</span>
                        </span>
                        <span data-bind="ifnot:log.anonymous">
                            <span data-bind="if: log.userURL">
                                <a class="overflow" data-bind="text: log.userFullName || log.apiKey, attr: {href: log.userURL}"></a>
                            </span>
                            <span data-bind="ifnot: log.userURL">
                                <span class="overflow" data-bind="text: log.userFullName"></span>
                            </span>
                        </span>
                        <!-- Log actions are the same as their template name -->
                        <span data-bind="template: {name: log.action, data: log}"></span>
                        <!-- /ko -->

                        <!-- For debugging purposes: If a log template for a the Log can't be found, show
                            an error message with its log action. -->
                        <!-- ko ifnot: log.hasTemplate() -->
                        <span class="text-warning">Could not render log: "<span data-bind="text: log.action"></span>"</span>
                        <!-- /ko -->

                    </dd>
                </dl><!-- end foreach logs -->
                  <a href="#{}"  data-bind="click: moreLogs, visible: enableMoreLogs">  Load more... </a>

            </div> 
        </div>
</div>


</div><!-- end #logScope -->
<%include file="_log_templates.mako"/>
