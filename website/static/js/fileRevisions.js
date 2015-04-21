'use strict';

var ko = require('knockout');
require('knockout.punches');
var $ = require('jquery');
var bootbox = require('bootbox');
var $osf = require('./osfHelpers');
var waterbutler = require('./waterbutler');

ko.punches.enableAll();

var urlParams = $osf.urlParams();

var Revision = function(data, index, file, node) {
    var self = this;
    var options = {};

    $.extend(self, data);

    if (urlParams.branch !== undefined) {
        options.branch = urlParams.branch;
    }
    options[self.versionIdentifier] = self.version;
    // Note: Google Drive version identifiers often begin with the same sequence
    self.displayVersion = file.provider === 'googledrive' ?
        self.version.substring(self.version.length - 8) :
        self.version.substring(0, 8);

    self.date = new $osf.FormattableDate(data.modified);
    self.displayDate = self.date.local !== 'Invalid date' ?
        self.date.local :
        data.date;

    // Append modification time to file name if OSF Storage and not current version
    if (file.provider === 'osfstorage' && file.name && index !== 0) {
        var parts = file.name.split('.');
        if (parts.length === 1) {
            options.displayName = parts[0] + '-' + data.modified;
        } else {
            options.displayName = parts.slice(0, parts.length - 1).join('') + '-' + data.modified + '.' + parts[parts.length - 1];
        }
    }

    self.osfViewUrl = '?' + $.param(options);
    self.osfDownloadUrl = '?' + $.param($.extend({action: 'download'}, options));
    self.waterbutlerDownloadUrl = waterbutler.buildDownloadUrl(file.path, file.provider, node.id, options);

    self.download = function() {
        window.location = self.waterbutlerDownloadUrl;
        return false;
    };
};

var RevisionsViewModel = function(node, file, editable) {
    var self = this;
    var fileExtra = file.extra || {};
    var revisionsOptions = {};

    if (urlParams.branch !== undefined) {
        fileExtra.branch = urlParams.branch;
        revisionsOptions.sha = urlParams.branch;
    }

    self.node = node;
    self.file = file;
    self.path = file.provider !== 'googledrive' ?
        file.path.split('/') :
        file.path.split('/').map(decodeURIComponent);

    // Hack: Set Figshare files to uneditable by default, then update after
    // fetching file metadata after revisions request fails
    self.editable = ko.observable(editable && file.provider !== 'figshare' && file.provider !== 'dataverse');
    self.urls = {
        delete: waterbutler.buildDeleteUrl(file.path, file.provider, node.id, fileExtra),
        download: waterbutler.buildDownloadUrl(file.path, file.provider, node.id, fileExtra),
        metadata: waterbutler.buildMetadataUrl(file.path, file.provider, node.id, revisionsOptions),
        revisions: waterbutler.buildRevisionsUrl(file.path, file.provider, node.id, revisionsOptions)
    };

    self.errorMessage = ko.observable('');
    self.currentVersion = ko.observable({});
    self.revisions = ko.observableArray([]);
    self.versioningSupported = ko.observable(true);

    self.userColumn = ko.computed(function() {
        return self.revisions()[0] &&
            self.revisions()[0].extra &&
            self.revisions()[0].extra.user;
    });
};

RevisionsViewModel.prototype.fetch = function() {
    var self = this;
    var request = $.getJSON(self.urls.revisions);

    request.done(function(response) {
        self.revisions(ko.utils.arrayMap(response.data, function(item, index) {
            if ($osf.urlParams()[item.versionIdentifier] === item.version) {
                self.currentVersion(new Revision(item, index, self.file, self.node));
                return self.currentVersion();
            }
            return new Revision(item, index, self.file, self.node);
        }));

        if (Object.keys(self.currentVersion()).length === 0) {
            self.currentVersion(self.revisions()[0]);
        }
    });

    request.fail(function(response) {
        self.versioningSupported(false);
        var err = response.responseJSON ?
            response.responseJSON.message || 'Unable to fetch versions' :
            'Unable to fetch versions';

        self.errorMessage(err);

        if (self.file.provider === 'figshare' || self.file.provider === 'dataverse') {
            // Hack for Figshare / Dataverse
            // only these addons will error on a revisions request
            // so dont allow downloads and set a fake current version
            $.ajax({
                method: 'GET',
                url: self.urls.metadata
            }).done(function(resp) {
                self.editable(resp.data.extra.canDelete);
            }).fail(function(xhr) {
                self.editable(false);
            });
        }

        self.currentVersion({
            osfViewUrl: '',
            osfDownloadUrl: '?action=download',
            download: function() {
                window.location = self.urls.download + '&' + $.param({displayName: self.file.name});
                return false;
            }
        });
    });
};

RevisionsViewModel.prototype.delete = function() {
    var self = this;
    $.ajax({
        type: 'DELETE',
        url: self.urls.delete,
    }).done(function() {
        window.location = self.node.urls.files;
    }).fail(function() {
        $osf.growl('Error', 'Could not delete file.');
    });
};

RevisionsViewModel.prototype.askDelete = function() {
    var self = this;
    bootbox.confirm({
        title: 'Delete file?',
        message: '<p class="overflow">' +
                'Are you sure you want to delete <strong>' +
                self.file.safeName + '</strong>?' +
            '</p>',
        callback: function(confirm) {
            if (confirm) {
                self.delete();
            }
        }
    });
};

RevisionsViewModel.prototype.isActive = function(version) {
    var self = this;

    if (self.currentVersion() === version) {
        return 'info';
    }
    return;
};

var RevisionTable = function(selector, node, file, editable) {

    var self = this;

    self.viewModel = new RevisionsViewModel(node, file, editable);
    self.viewModel.fetch();
    $osf.applyBindings(self.viewModel, selector);

};

module.exports = RevisionTable;
