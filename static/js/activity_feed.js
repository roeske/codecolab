(function() {
    window.ActivityFeed = (function() {

        ActivityFeed.prototype.toggle                   = null;
        ActivityFeed.prototype.toggle_icon_show         = null;
        ActivityFeed.prototype.toggle_icon_hide         = null;
        ActivityFeed.prototype.list                     = null;
        ActivityFeed.prototype.list_container           = null;
        ActivityFeed.prototype.container                = null;
        ActivityFeed.prototype.project_name             = null;
        ActivityFeed.prototype.piles                    = null;
        ActivityFeed.prototype.user_id                  = null;

        function ActivityFeed(options) { 
            // copy parameters
            _.extend(this, options);
            this.list.data('_user_id', options.user_id);

            var that = this;

            // setup toggling
            this.toggle_icon_show.hide();
            this.toggle_icon_hide.show();

            this.toggle.click(function() {
                var is_visible = $(this).data('is-visible');
                if (is_visible || is_visible == 'true') {
                    that.hide();
                    is_visible = false;
                } else {
                    that.show();
                    is_visible = true;
                }
                // todo: refactor
                $(this).data('is-visible', is_visible);
            });

            this._connect_activity_links();

            // setup activity paginator:
            this.list.jscroll({ 
                nextSelector: '.activity_paginator',
                callback: this._connect_activity_links,
                loadingHtml: '<p class="activity_loading">Loading...<img src="/assets/loading.gif" height="24px" width="24px" style="float: right;"></img></p>'
            });
        }

        ActivityFeed.prototype._connect_activity_links = function() {
            var user_id = $('#activity_list').data('_user_id');

            $("a.activity_card").each(function(i, elem) {
                // TODO: Refactor
                var obj = $(elem);
                cc_connect_card_to_modal(obj.text(), this.project_name, 
                                         obj, true);
            });



            $(".activity_username").click(function(e) {
                e.preventDefault();
                var url = $(this).attr("href");
                var tokens = url.split("/");
                
                if (tokens[tokens.length - 1] == user_id) {
                    show_profile_dialog(url);
                } else {
                    show_other_profile_dialog(url);
                }
                return false;
            });

        };

        ActivityFeed.prototype.reload = function() {
            var url = "/project/" + this.project_name + "/activity";
            var that = this;
            $.get(url, function(data) {
                that.list.html(data);
                that.list.animate({scrollTop: 0}, "fast");
                that._connect_activity_links();
            });
        };

        ActivityFeed.prototype.show = function() {
            this.toggle_icon_show.hide();
            this.toggle_icon_hide.show();
            this.list_container.show();

            $("#piles").width("84%");
            $("#activity_container").width("16%");
            $("#activity_toggle").width("7%");
        };

        ActivityFeed.prototype.hide = function() {
            this.toggle_icon_show.show();
            this.toggle_icon_hide.hide();
            this.list_container.hide();

            $("#piles").width("99%");
            $("#activity_container").width("1%");
            $("#activity_toggle").width("100%");
        };

        return ActivityFeed;
    })();

}).call(this);
