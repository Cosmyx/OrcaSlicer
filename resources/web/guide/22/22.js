var m_ProfileItem;
var FilamentPriority=new Array( "pla","abs","pet","tpu","pc");
var VendorPriority=new Array("generic");

function OnInit()
{
  $("#printerBtn").on("click", function(){
    $("#MachineList").slideToggle(300);
    $(this).find(".CArrow").toggleClass("active");
  });

  $("#filatypeBtn").on("click", function(){
    $("#FilatypeList").slideToggle(300);
    $(this).find(".CArrow").toggleClass("active");
  });

  $("#vendorBtn").on("click", function(){
    $("#VendorList").slideToggle(300);
    $(this).find(".CArrow").toggleClass("active");
  });

  $('#SelectAllCheckbox').change(function() {
    if ($(this).is(':checked')) {
      SelectAllFilament(1);
    } else {
      SelectAllFilament(0);
    }
  });

  TranslatePage();
  RequestProfile();
}

function RequestProfile()
{
	var tSend={};
	tSend['sequence_id']=Math.round(new Date() / 1000);
	tSend['command']="request_userguide_profile";

	SendWXMessage( JSON.stringify(tSend) );
}

function HandleStudio(pVal)
{
	let strCmd=pVal['command'];

	if(strCmd=='response_userguide_profile')
	{
		m_ProfileItem=pVal['response'];
		SortUI();
	}
}

function GetFilamentShortname( sName )
{
	let sShort=sName.split('@')[0].trim();

	return sShort;
}


function ChooseAllMachine()
{
	let bCheck=$("#MachineList input:first").prop("checked");

	$("#MachineList input").prop("checked",bCheck);

	SortFilament();
}


function ChooseAllFilament()
{
	let bCheck=$("#FilatypeList input:first").prop("checked");
	$("#FilatypeList input").prop("checked",bCheck);

	SortFilament();
}

function ChooseAllVendor()
{
	let bCheck=$("#VendorList input:first").prop("checked");
	$("#VendorList input").prop("checked",bCheck);

	SortFilament();
}

function MachineClick()
{
	let nChecked=$("#MachineList input:gt(0):checked").length
	let nAll    =$("#MachineList input:gt(0)").length

	if(nAll==nChecked)
	{
		$("#MachineList input:first").prop("checked",true);
	}
	else
	{
		$("#MachineList input:first").prop("checked",false);
	}

	SortFilament();
}

function FilaClick()
{
	let nChecked=$("#FilatypeList input:gt(0):checked").length
	let nAll    =$("#FilatypeList input:gt(0)").length

	if(nAll==nChecked)
	{
		$("#FilatypeList input:first").prop("checked",true);
	}
	else
	{
		$("#FilatypeList input:first").prop("checked",false);
	}

	SortFilament();
}

function VendorClick()
{
	let nChecked=$("#VendorList input:gt(0):checked").length
	let nAll    =$("#VendorList input:gt(0)").length

	if(nAll==nChecked)
	{
		$("#VendorList input:first").prop("checked",true);
	}
	else
	{
		$("#VendorList input:first").prop("checked",false);
	}

	SortFilament();
}

function SortFilament()
{
	let FilaNodes=$("#ItemBlockArea div");
	let nFilament=FilaNodes.length;

	//ModelList
	let pModel=$("#MachineList input:checked");
	let nModel=pModel.length;
	let ModelList=new Array();
	for(let n=0;n<nModel;n++)
	{
		let OneModel=pModel[n];

		let mName=OneModel.getAttribute("mode");
		if( mName=='all' )
		{
			continue;
		}
		else
		{
			let mNozzle=OneModel.getAttribute("nozzle");
			let NozzleArray=mNozzle.split(';');

			for( let bb=0;bb<NozzleArray.length;bb++ )
			{
				let NewModel='['+mName+'++'+NozzleArray[bb]+']';

				ModelList.push( NewModel );
			}
		}
	}

	//TypeList
	let pType=$("#FilatypeList input:gt(0):checked");
	let nType=pType.length;
	let TypeList=new Array();
	for(let n=0;n<nType;n++)
	{
		let OneType=pType[n];
		TypeList.push(  OneType.getAttribute("filatype") );
	}

	//VendorList
	let pVendor=$("#VendorList input:gt(0):checked");
	let nVendor=pVendor.length;
	let VendorList=new Array();
	for(let n=0;n<nVendor;n++)
	{
		let OneVendor=pVendor[n];
		VendorList.push(  OneVendor.getAttribute("vendor") );
	}


	//Update Filament UI
	for(let m=0;m<nFilament;m++)
	{
		let OneNode=FilaNodes[m];
		let OneFF=OneNode.getElementsByTagName("input")[0];

	  let fModel=OneFF.getAttribute("model");
		let fVendor=OneFF.getAttribute("vendor");
		let fType=OneFF.getAttribute("filatype");

		if(TypeList.in_array(fType) && VendorList.in_array(fVendor))
		{
			let HasModel=false;
			for(let m=0;m<ModelList.length;m++)
			{
				let ModelSrc=ModelList[m];

				if( fModel.indexOf(ModelSrc)>=0)
				{
					HasModel=true;
					break;
				}
			}

			if(HasModel || fModel=='')
			    $(OneNode).show();
			else
				$(OneNode).hide();
		}
		else
			$(OneNode).hide();
	}
}

function SelectAllFilament( nShow )
{
	if( nShow==0 )
	{
		$('#ItemBlockArea input').prop("checked",false);
	}
	else
	{
		$('#ItemBlockArea input').prop("checked",true);
	}
}

function ShowNotice( nShow )
{
	if(nShow==0)
	{
		$("#NoticeMask").hide();
		$("#NoticeBody").hide();
	}
	else
	{
		$("#NoticeMask").show();
		$("#NoticeBody").show();
	}
}

function SortUI()
{
	var ModelList=new Array();

	let nMode=m_ProfileItem["model"].length;
	for(let n=0;n<nMode;n++)
	{
		let OneMode=m_ProfileItem["model"][n];

		if( OneMode["nozzle_selected"]!="" )
			ModelList.push(OneMode);
	}

	//model
	let HtmlMode='';
	nMode=ModelList.length;
	for(let n=0;n<nMode;n++)
	{
		let sModel=ModelList[n];

		HtmlMode+='<div class="checkboxText"><input class="inputIndent" type="checkbox" mode="'+sModel['model']+'"  nozzle="'+sModel['nozzle_selected']+'"   onChange="MachineClick()" />'+sModel['model']+'</div>';
	}

	$('#MachineList').append(HtmlMode);
	$('#MachineList input').prop("checked",true);
	if(nMode<=1)
	{
		$('#MachineList').hide();
	}

	//Filament
	let SelectNumber=0;

	var TypeHtmlArray={};
    var VendorHtmlArray={};
	var GenericFilamentHtmlArray={};
	var NonGenericFilamentHtmlArray={};
	for( let key in m_ProfileItem['filament'] )
	{
		let OneFila=m_ProfileItem['filament'][key];

		let fWholeName=OneFila['name'].trim();
		let fShortName=GetFilamentShortname( OneFila['name'] );
		let fVendor=OneFila['vendor'];
		let fType=OneFila['type'];
		let fSelect=OneFila['selected'];
		let fModel=OneFila['models']


    let bFind=false;
		if( fModel=='')
		{
			bFind=true;
		}
		else
		{
			//check in modellist
      let nModelAll=ModelList.length;
      for(let m=0;m<nModelAll;m++)
      {
        let sOne=ModelList[m];

        let OneName=sOne['model'];
        let NozzleArray=sOne["nozzle_selected"].split(';');

        let nNozzle=NozzleArray.length;

        for( let b=0;b<nNozzle;b++ )
        {
          let nowModel= OneName+"++"+NozzleArray[b];
          if(fModel.indexOf(nowModel)>=0)
          {
            bFind=true;
            break;
          }
        }
			}
		}

		if(bFind)
		{
			//Type
			let LowType=fType.toLowerCase();
		    if(!TypeHtmlArray.hasOwnProperty(LowType))
		    {
			    let HtmlType='<div class="checkboxText"><input class="inputIndent" type="checkbox" filatype="'+fType+'" onChange="FilaClick()"   />'+fType+'</div>';

				TypeHtmlArray[LowType]=HtmlType;
		    }

			//Vendor
			let lowVendor=fVendor.toLowerCase();
			if(!VendorHtmlArray.hasOwnProperty(lowVendor))
		    {
			    let HtmlVendor='<div class="checkboxText"><input class="inputIndent" type="checkbox" vendor="'+fVendor+'"  onChange="VendorClick()" />'+fVendor+'</div>';

				VendorHtmlArray[lowVendor]=HtmlVendor;
		    }

			//Filament
			let pFila=$("#ItemBlockArea input[vendor='"+fVendor+"'][filatype='"+fType+"'][name='"+fShortName+"']");
	        if(pFila.length==0)
		    {
			    let HtmlFila='<div><input type="checkbox" vendor="'+fVendor+'"  filatype="'+fType+'" filalist="'+fWholeName+';'+'"  model="'+fModel+'" name="'+fShortName+'" />'+fShortName+'</div>';

			    // Separate generic and non-generic filaments (generic shown first)
			    if(fVendor.toLowerCase() === 'generic') {
				    GenericFilamentHtmlArray[fShortName] = HtmlFila;
			    } else {
				    NonGenericFilamentHtmlArray[fShortName] = HtmlFila;
			    }
		    }
			else
			{
				let strModel=pFila.attr("model");
				let strFilalist=pFila.attr("filalist");

				if(strModel == '' || fModel == '')
					pFila.attr("model", '');
				else
					pFila.attr("model", strModel+fModel);

				pFila.attr("filalist", strFilalist+fWholeName+';');
			}

		    if(fSelect*1==1)
			{
				$("#ItemBlockArea input[vendor='"+fVendor+"'][filatype='"+fType+"'][name='"+fShortName+"']").prop("checked",true);
				SelectNumber++;
			}
		}
	}

	// Append filaments: generic first, then non-generic
	for(let key in GenericFilamentHtmlArray) {
		$("#ItemBlockArea").append(GenericFilamentHtmlArray[key]);
	}
	for(let key in NonGenericFilamentHtmlArray) {
		$("#ItemBlockArea").append(NonGenericFilamentHtmlArray[key]);
	}

	//Sort TypeArray
	let TypeAdvNum=FilamentPriority.length;
	for( let n=0;n<TypeAdvNum;n++ )
	{
		let strType=FilamentPriority[n];

		if( TypeHtmlArray.hasOwnProperty( strType ) )
		{
			$("#FilatypeList").append( TypeHtmlArray[strType] );
			delete( TypeHtmlArray[strType] );
		}
	}
    for(let key in TypeHtmlArray )
	{
		$("#FilatypeList").append( TypeHtmlArray[key] );
	}
	$("#FilatypeList input").prop("checked",true);

	//Sort VendorArray
	let VendorAdvNum=VendorPriority.length;
	for( let n=0;n<VendorAdvNum;n++ )
	{
		let strVendor=VendorPriority[n];

		if( VendorHtmlArray.hasOwnProperty( strVendor ) )
		{
			$("#VendorList").append( VendorHtmlArray[strVendor] );
			delete( VendorHtmlArray[strVendor] );
		}
	}
    for(let key in VendorHtmlArray )
	{
		$("#VendorList").append( VendorHtmlArray[key] );
	}
	$("#VendorList input").prop("checked",true);

	//------
	if(SelectNumber==0)
		ChooseDefaultFilament();

	//--If Need Install Network Plugin
	if(m_ProfileItem["network_plugin_install"]!='1' || (m_ProfileItem["network_plugin_install"]=='1' && m_ProfileItem["network_plugin_compability"]=='0') )
	{
		$("#AcceptBtn").show();
		$("#GotoNetPluginBtn").hide();
	}
}

function ResponseFilamentResult()
{
	let FilaSelectedList= $("#ItemBlockArea input:checked");
	let nAll=FilaSelectedList.length;

	if( nAll==0 )
	{
		ShowNotice(1);
		return false;
	}

	let FilaArray=new Array();
	for(let n=0;n<nAll;n++)
	{
		let sName=FilaSelectedList[n].getAttribute("name");

	    for( let key in m_ProfileItem['filament'] )
	    {
			let FName=GetFilamentShortname(key);

			if(FName==sName)
				FilaArray.push(key);
		}
	}

	var tSend={};
	tSend['sequence_id']=Math.round(new Date() / 1000);
	tSend['command']="save_userguide_filaments";
	tSend['data']={};
	tSend['data']['filament']=FilaArray;

	SendWXMessage( JSON.stringify(tSend) );

	return true;
}

function ReturnPreviewPage()
{
	let nMode=m_ProfileItem["model"].length;

	if( nMode==1)
		document.location.href="../1/index.html";
	else
		document.location.href="../21/index.html";
}

function GotoNetPluginPage()
{
	let bRet=ResponseFilamentResult();

	if(bRet)
		window.location.href="../4orca/index.html";
}

function FinishGuide()
{
	let bRet=ResponseFilamentResult();

	if(bRet)
	{
		var tSend={};
		tSend['sequence_id']=Math.round(new Date() / 1000);
		tSend['command']="user_guide_finish";
		tSend['data']={};
		tSend['data']['action']="finish";

		SendWXMessage( JSON.stringify(tSend) );
	}
}

function ChooseDefaultFilament()
{
	//ModelList
	let pModel=$("#MachineList input:gt(0)");
	let nModel=pModel.length;
	let ModelList=new Array();
	for(let n=0;n<nModel;n++)
	{
		let OneModel=pModel[n];
		ModelList.push(  OneModel.getAttribute("mode") );
	}

	//DefaultMaterialList
	let DefaultMaterialString=new Array();
	let nMode=m_ProfileItem["model"].length;
	for(let n=0;n<nMode;n++)
	{
		let OneMode=m_ProfileItem["model"][n];
		let ModeName=OneMode['model'];

		if( ModelList.indexOf(ModeName)>-1 )
		{
			DefaultMaterialString+=OneMode['materials']+';';
		}
	}

	let DefaultMaterialArray=DefaultMaterialString.split(';');

	//Filament
	let FilaNodes=$("#ItemBlockArea input");
    let nFilament=FilaNodes.length;
    for(let m=0;m<nFilament;m++)
	{
		let OneFF=FilaNodes[m];
		$(OneFF).prop("checked",false);

	  let filamentList=OneFF.getAttribute("filalist");
		let filamentArray=filamentList.split(';')

		let HasModel=false;
		let NowFilaLength=filamentArray.length;
		for(let p=0;p<NowFilaLength;p++)
		{
			let NowFila=filamentArray[p];

			if( NowFila!='' && DefaultMaterialArray.indexOf(NowFila)>-1)
			{
				HasModel=true;
				break;
			}
		}

		if(HasModel)
		    $(OneFF).prop("checked",true);
	}

	ShowNotice(0);
}
