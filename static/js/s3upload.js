// requires lodash.js
(function() {
  window.S3Upload = (function() {
    S3Upload.prototype.s3_object_name = "default_object";
    S3Upload.prototype.s3_sign_put_url = '/signS3put';
    S3Upload.prototype.file_dom_selector = '#file_upload';

    S3Upload.prototype.onFinishS3Put = function(public_url) {
      return console.log('base.onFinishS3Put()', public_url);
    };

    S3Upload.prototype.onProgress = function(percent, status) {
      return console.log('base.onProgress()', percent, status);
    };

    S3Upload.prototype.onError = function(status) {
      return console.log('base.onError()', status);
    };

    function S3Upload(options, s3_object_name) {
      if (options == null) options = {};
      console.log(options);
      _.extend(this, options);
      this.s3_object_name = s3_object_name;
      this.handleFileSelect(jQuery(this.file_dom_selector).get(0));
    }

    S3Upload.prototype.safeMimeType = function(mime_type) {
      // application/octet-stream can be used for unknown filetypes, per
      // RFC 2046: 'The "octet-stream" subtype is used to indicate that
      // a body contains arbitrary binary data'
      //
      // see: http://stackoverflow.com/questions/1176022/unknown-file-type-mime
      // 
      // Without this code, the upload fails in chrome and probably other
      // browsers for simple things like .json files. Of course, we could
      // get more elaborate with mimetypes here, but we at least need
      // to fall back on a valid one.
      //
      // Fallback on application/octet-stream if filetype is unknown or
      // upload will fail.

      if (mime_type == '') {
        return "binary/octet-stream";
      } else {
        return mime_type;
      }
    }

    S3Upload.prototype.handleFileSelect = function(file_element) {
      var f, files, output, _i, _len, _results;
      this.onProgress(0, 'Upload started.');
      files = file_element.files;
      output = [];
      _results = [];
      for (_i = 0, _len = files.length; _i < _len; _i++) {
        f = files[_i];
        _results.push(this.uploadFile(f));
      }
      return _results;
    };

    S3Upload.prototype.createCORSRequest = function(method, url) {
      var xhr;
      xhr = new XMLHttpRequest();
      if (xhr.withCredentials != null) {
        xhr.open(method, url, true);
      } else if (typeof XDomainRequest !== "undefined") {
        xhr = new XDomainRequest();
        xhr.open(method, url);
      } else {
        xhr = null;
      }
      return xhr;
    };

    S3Upload.prototype.executeOnSignedUrl = function(file, callback) {
      var this_s3upload, xhr;
      this_s3upload = this;
      xhr = new XMLHttpRequest();

      var file_type = this.safeMimeType(file.type);
      xhr.open('GET', this.s3_sign_put_url + '?s3_object_type=' + file_type + '&s3_object_name=' + this.s3_object_name, true);
      xhr.overrideMimeType('text/plain; charset=x-user-defined');
      xhr.onreadystatechange = function(e) {
        var result;
        if (this.readyState === 4 && this.status === 200) {
          try {
            result = JSON.parse(this.responseText);
          } catch (error) {
            this_s3upload.onError('Signing server returned some ugly/empty JSON: "' + this.responseText + '"');
            return false;
          }
          console.log('url='+result.url)
          return callback(decodeURIComponent(result.signed_request), result.url);
        } else if (this.readyState === 4 && this.status !== 200) {
          return this_s3upload.onError('Could not contact request signing server. Status = ' + this.status);
        }
      };
      return xhr.send();
    };

    S3Upload.prototype.uploadToS3 = function(file, url, public_url) {
      var this_s3upload, xhr;
      this_s3upload = this;
      xhr = this.createCORSRequest('PUT', url);
      if (!xhr) {
        this.onError('CORS not supported');
      } else {
        xhr.onload = function() {
          if (xhr.status === 200) {
            this_s3upload.onProgress(100, 'Upload completed.');
            return this_s3upload.onFinishS3Put(public_url);
          } else {
            return this_s3upload.onError('Upload error: ' + xhr.status);
          }
        };
        xhr.onerror = function() {
          return this_s3upload.onError('XHR error.');
        };
        xhr.upload.onprogress = function(e) {
          var percentLoaded;
          if (e.lengthComputable) {
            percentLoaded = Math.round((e.loaded / e.total) * 100);
            return this_s3upload.onProgress(percentLoaded, percentLoaded === 100 ? 'Finalizing.' : 'Uploading.');
          }
        };
      }
      var file_type = this.safeMimeType(file.type);
      xhr.setRequestHeader('Content-Type', file_type);
      xhr.setRequestHeader('x-amz-acl', 'public-read');
      return xhr.send(file);
    };

    S3Upload.prototype.uploadFile = function(file) {
      var this_s3upload;
      this_s3upload = this;
      return this.executeOnSignedUrl(file, function(signedURL, publicURL) {
        return this_s3upload.uploadToS3(file, signedURL, publicURL);
      });
    };

    return S3Upload;

  })();

}).call(this);
