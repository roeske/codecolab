/**
 * Prototype for ReportsPage object. This is the client-side controller
 * for the reports page.
 */
(function() {
    window.ReportsPage = (function() {

        ReportsPage.prototype.dialog_height = 480;
        ReportsPage.prototype.dialog_width = 600;
        ReportsPage.prototype.default_dialog_title = 'Report'; 
        ReportsPage.prototype.section_team_reports = null;
        ReportsPage.prototype.section_create_report = null;
        ReportsPage.prototype.is_team_reports_shown = true;
        ReportsPage.prototype.tab_create_report = null;
        ReportsPage.prototype.tab_team_reports = null;
        ReportsPage.prototype.reports_accordion = null;
        ReportsPage.prototype.report_edit_url = null;

        function ReportsPage(options) { 
            this.report_edit_url = options.report_edit_url;

            // Reference sections.
            this.section_create_report = require(".section_create_report"); 
            this.section_team_reports = require(".section_team_reports");
           
            // Reference tabs.
            this.tab_create_report = require("#tab_create_report");
            this.tab_team_reports = require("#tab_team_reports");
            this.reports_accordion = require(".reports_accordion");

            // Reference outer scope.
            var that = this;

            var setup = function(elem, is_first) {
                // Setup accordion
                if (!is_first) {
                    elem.accordion('destroy');
                }
                elem.accordion({
                    header: '.report_header',
                    heightStyle: 'content'
                }).jscroll({ 
                    nextSelector: '.reports_paginator',
                    callback: function() {
                        setup(elem, false);
                    }
                });
            };
            setup(this.reports_accordion, true);

            // If the team reports tab is clicked, but the section is not
            // already shown, show it.
            this.tab_team_reports.click(function() {
                if(!that.is_team_reports_shown) {
                    that.show_team_reports();
                }
            });

            // If the create report tab is clicked, but the section is not
            // already shown, show it.
            this.tab_create_report.click(function() {
                if(that.is_team_reports_shown) {
                    that.show_create_report();
                }
            });

            // Make sure initial state reflects what is really shown.
            /*
            if (this.is_team_reports_shown) {
                this.show_team_reports();
            } else {
                this.show_create_report();
            }
            */

            // Keep team reports at window height
            jQuery(window).bind('resize', function() { 
                that.fit_to_window(that.reports_accordion);
            });
            that.fit_to_window(that.reports_accordion);

            this._setup_editable_reports();
        }

        ReportsPage.prototype._setup_editable_reports = function() {
            alert(this.report_edit_url);
            var that = this;
            jQuery(".editable_report").each(function(i, value) {
                var report_id = $(value).data('id');
                var url = that.report_edit_url + report_id;


                jQuery(value).editable(url, {
                    type: "textarea",
                    name: "text",
                    event: "click",
                    tooltip: "Click to edit...",
                    cssclass: "jeditable",
                    height: "7em",
                    submit: "save",
                    onblur: "cancel",
                    loadurl: url
                });
            });
        };

        ReportsPage.prototype.fit_to_window = function(view) {
            var window_height = jQuery(window).height();
            console.log(window_height);
            view.height(window_height * 0.87);
        };

        ReportsPage.prototype.show_team_reports = function() {
            this.tab_create_report.removeClass("active");
            this.tab_team_reports.addClass("active");

            this.is_team_reports_shown = true;
            this.section_create_report.hide();
            this.section_team_reports.show();
        };

        ReportsPage.prototype.show_create_report = function() {
            this.tab_create_report.addClass("active");
            this.tab_team_reports.removeClass("active");

            this.is_team_reports_shown = false;
            this.section_create_report.show();
            this.section_team_reports.hide();
        };

        return ReportsPage;
    })();
}).call(this);
