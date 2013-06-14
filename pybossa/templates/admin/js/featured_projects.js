<script type=text/javascript>
  $SCRIPT_ROOT = {{ request.script_root|tojson|safe }};
  function add(project_id) {
      var url = $SCRIPT_ROOT + "/admin/featured/" + project_id;
      var xhr = $.ajax({
          type: 'POST',
          url: url,
          dataType: 'json',
      });
      xhr.done(function(){
          $("#projectBtnDel" + project_id).show();
          $("#projectBtnAdd" + project_id).hide();
      });
  }
  function del(project_id) {
      var url = $SCRIPT_ROOT + "/admin/featured/" + project_id;
      var xhr = $.ajax({
          type: 'DELETE',
          url: url,
          dataType: 'json',
      });
      xhr.done(function(){
          $("#projectBtnDel" + project_id).hide();
          $("#projectBtnAdd" + project_id).show();

      });
  }
</script>

