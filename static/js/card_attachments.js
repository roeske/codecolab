function get_filename_from_input(input) {
  var fullPath = input.val();

  if (fullPath) {
    var startIndex = (fullPath.indexOf('\\') >= 0 ? 
    fullPath.lastIndexOf('\\') : fullPath.lastIndexOf('/'));
    var filename = fullPath.substring(startIndex);

    if (filename.indexOf('\\') === 0 || filename.indexOf('/') === 0) {
      filename = filename.substring(1);
    }

    return filename;
  }

  return "unknown";
}
