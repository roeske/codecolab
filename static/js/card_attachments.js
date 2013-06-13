/**
 * Prototype for CardAttachments object. This allows the user
 * to upload a file directly via Amazon S3 and then attach it to
 * a card. Attachments are then made visible in the card
 * automatically via the save_and_reload() method.
 */
(function() {
    window.CardAttachments = (function() {
        CardAttachments.prototype.project_name      = null;
        CardAttachments.prototype.card_id           = null;
        CardAttachments.prototype.file_input        = null; CardAttachments.prototype.progress_bar      = null;
        CardAttachments.prototype.card_attachments  = null;


        function CardAttachments(options) {
            // copy parameters
            _.extend(this, options);

            var that = this;
            // register change listener for when user selects file.
            jQuery(this.file_input).change(function() {
                var filename = that.get_filename();
                that.s3_upload(filename);
            });
        }


        CardAttachments.prototype.s3_upload = function(filename) {
            var that = this;
            var s3upload = new S3Upload({
                file_dom_selector: this.file_input,
                s3_sign_put_url: '/sign_s3_upload/',

                onProgress: function(percent, message) { 
                    jQuery(that.progress_bar).width(percent);
                },

                onFinishS3Put: function(url) { 
                    console.log("onFinishS3Put: finish: ", url);
                    that.save_and_reload(url, filename);
                    jQuery(that.progress_bar).width(0);
                },

                onError: function(status) {
                    alert("Error uploading file. Please try again.");
                    jQuery(that.file_input).val("");
                    jQuery(that.progress_bar).width(0);
                }

            }, filename);
        };


        CardAttachments.prototype.get_filename = function(file_input) {
            var fullPath = jQuery(this.file_input).val();

            if (fullPath) {
                var startIndex = (fullPath.indexOf('\\') >= 0 ? 
                    fullPath.lastIndexOf('\\') : fullPath.lastIndexOf('/'));

                var filename = fullPath.substring(startIndex);

                if (filename.indexOf('\\') === 0 || filename.indexOf('/') === 0) {
                    filename = filename.substring(1);
                }

                return filename;
            }

            return "unknown_filename";
        };


        CardAttachments.prototype.save_and_reload = function(url, filename) {
            var api_url = this.project_name + "/cards/" + this.card_id + "/attachments";

            var data = JSON.stringify({url: url, filename: filename});

            var that = this;
            $.ajax({
                type: "POST",
                url: api_url,
                data: data, 
                success: function(data) {
                    jQuery(that.card_attachments).replaceWith(data);
                },
                failure: function(data) {
                    alert("Failed to refresh attachments. Please reload the page.");
                },
                dataType: "html",
                contentType: "application/json;charset=UTF-8"
            });
        };

        return CardAttachments;
    })();

}).call(this);

