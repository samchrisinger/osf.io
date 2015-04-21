'use strict';

var m = require('mithril');
var URI = require('URIjs');
var $ = require('jquery');

var Fangorn = require('js/fangorn');
var waterbutler = require('js/waterbutler');

function changeState(grid, item, state) {
    item.data.state = state;
    grid.updateFolder(null, item);
}

function _downloadEvent(event, item, col) {
    event.stopPropagation();
    window.location = waterbutler.buildTreeBeardDownload(item, {path: item.data.extra.fileId});
}

// Define Fangorn Button Actions
function _fangornActionColumn (item, col) {
    var self = this;
    var buttons = [];

    function dataversePublish(event, item, col) {
        var self = this; // treebeard
        var both = !item.data.dataverseIsPublished;
        var url = both ? item.data.urls.publishBoth : item.data.urls.publish;
        var toPublish = both ? 'Dataverse and dataset' : 'dataset';
        var modalContent = [
            m('h3', 'Publish this ' + toPublish + '?'),
            m('p.m-md', both ? 'This dataset cannot be published until ' + item.data.dataverse + ' Dataverse is published. ' : ''),
            m('p.m-md', 'By publishing this ' + toPublish + ', all content will be made available through the Harvard Dataverse using their internal privacy settings, regardless of your OSF project settings. '),
            m('p.font-thick.m-md', both ? 'Do you want to publish this Dataverse AND this dataset?' : 'Are you sure you want to publish this dataset?')
        ];
        var modalActions = [
            m('button.btn.btn-default.m-sm', { 'onclick' : function (){ self.modal.dismiss(); }},'Cancel'),
            m('button.btn.btn-primary.m-sm', { 'onclick' : function() { publishDataset(); } }, 'Publish ' + toPublish)
        ];

        this.modal.update(modalContent, modalActions);

        function publishDataset() {
            self.modal.dismiss();
            item.notify.update('Publishing ' + toPublish, 'info', 1, 1);
            $.osf.putJSON(
                url,
                {}
            ).done(function(data) {
                item.notify.update();
                var modalContent = [
                    m('p.m-md', 'Your content has been published.')
                ];
                var modalActions = [
                    m('button.btn.btn-primary.m-sm', { 'onclick' : function() { self.modal.dismiss(); } }, 'Okay')
                ];
                self.modal.update(modalContent, modalActions);
                item.data.hasPublishedFiles = item.children.length > 0;
                item.data.state = item.data.hasPublishedFiles ? 'published' : 'draft';
            }).fail(function(xhr, status, error) {
                var statusCode = xhr.responseJSON.code;
                var message;
                switch (statusCode) {
                    case 405:
                        message = 'Error: This dataset cannot be published until ' + item.data.dataverse + ' Dataverse is published.';
                        break;
                    case 409:
                        message = 'This dataset version has already been published.';
                        break;
                    default:
                        message = 'Error: Something went wrong when attempting to publish your dataset.';
                        Raven.captureMessage('Could not publish dataset', {
                            url: url,
                            textStatus: status,
                            error: error
                        });
                }

                var modalContent = [
                    m('p.m-md', message)
                ];
                var modalActions = [
                    m('button.btn.btn-primary.m-sm', { 'onclick' : function() { self.modal.dismiss(); } }, 'Okay')
                ];
                self.modal.update(modalContent, modalActions);
            });
        }
    }

    if (item.kind === 'folder' && item.data.addonFullname && item.data.state === 'draft' && item.data.permissions.edit) {
        buttons.push(
            {
                'name' : '',
                'tooltip' : 'Upload file',
                'icon' : 'fa fa-upload',
                'css' : 'fangorn-clickable btn btn-default btn-xs',
                'onclick' : Fangorn.ButtonEvents._uploadEvent
            },
            {
                'name' : '',
                'tooltip' : 'Publish Dataset',
                'icon' : 'fa fa-globe',
                'css' : 'btn btn-primary btn-xs',
                'onclick' : dataversePublish
            }
        );
    } else if (item.kind === 'file') {
        buttons.push({
            name : '',
            'tooltip' : 'Download file',
            icon : 'fa fa-download',
            css : 'btn btn-info btn-xs',
            onclick: _downloadEvent
        });
        if (item.parent().data.state === 'draft' && item.data.permissions.edit) {
            buttons.push({
                name: '',
                tooltip : 'Delete',
                icon: 'fa fa-times',
                css: 'm-l-lg text-danger fg-hover-hide',
                style: 'display:none',
                onclick: Fangorn.ButtonEvents._removeEvent
            });
        }
    }
    return buttons.map(function(btn){
                return m('i', { 'data-col' : item.id, 'class' : btn.css, 'data-toggle' : 'tooltip', title : btn.tooltip, 'data-placement': 'bottom',  style : btn.style, 'onclick' : function(event){ btn.onclick.call(self, event, item, col); } },
                    [ m('span', { 'class' : btn.icon}, btn.name) ]);
            });
    
}

function _fangornDataverseTitle(item, col) {
    var tb = this;
    if (item.data.addonFullname) {
        var contents = [m('dataverse-name', item.data.name + ' ')];
        if (item.data.hasPublishedFiles) {
            if (item.data.permissions.edit) {
                var options = [
                    m('option', {selected: item.data.state === 'published', value: 'published'}, 'Published'),
                    m('option', {selected: item.data.state === 'draft', value: 'draft'}, 'Draft')
                ];
                contents.push(
                    m('span', [
                        m('select', {
                            class: 'dataverse-state-select',
                            onchange: function(e) {
                                changeState(tb, item, e.target.value);
                            }
                        }, options)
                    ])
                );
            } else {
                contents.push(
                    m('span.text-muted', '[Published]')
                );
            }
        } else {
            contents.push(
                m('span.text.text-muted', '[Draft]')
            );
        }
        return m('span', contents);
    } else {
        return m('span',[
            m('dataverse-name', {
                onclick: function() {
                    var redir = new URI(item.data.nodeUrl);
                    window.location = redir
                        .segment('files')
                        .segment(item.data.provider)
                        .segment(item.data.extra.fileId)
                        .toString();
                },
                'data-toggle': 'tooltip',
                title: 'View file',
                'data-placement': 'bottom'
            }, item.data.name
             )
        ]);
    }
}

function _fangornColumns(item) {
    var selectClass = '';
    var tb = this;
    if (item.data.kind === 'file' && tb.currentFileID === item.id) {
        selectClass = 'fangorn-hover';
    }

    var columns = [];
    columns.push({
        data : 'name',
        folderIcons : true,
        filter : true,
        css: selectClass,
        custom: _fangornDataverseTitle
    });

    if (this.options.placement === 'project-files') {
        columns.push(
            {
                css: 'action-col',
                filter: false,
                custom: _fangornActionColumn
            },
            {
                data: 'downloads',
                filter: false,
                css: ''
            }
        );
    }

    return columns;
}


function _fangornFolderIcons(item){
    if(item.data.iconUrl){
        return m('img',{src:item.data.iconUrl, style:{width:'16px', height:'auto'}}, ' ');
    }
    return undefined;
}

function _fangornDeleteUrl(item) {
    return waterbutler.buildTreeBeardDelete(item, {full_path: item.data.path + '?' + $.param({name: item.data.name})});
}

function _fangornLazyLoad(item) {
    return waterbutler.buildTreeBeardMetadata(item, {state: item.data.state});
}

function _canDrop(item) {
    return item.data.provider &&
        item.kind === 'folder' &&
        item.data.permissions.edit &&
        item.data.state === 'draft'
}

Fangorn.config.dataverse = {
    folderIcon: _fangornFolderIcons,
    resolveDeleteUrl: _fangornDeleteUrl,
    resolveRows: _fangornColumns,
    lazyload: _fangornLazyLoad,
    canDrop: _canDrop
};
