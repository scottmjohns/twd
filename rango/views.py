from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext
from django.shortcuts import render_to_response, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from rango.models import Category
from rango.models import Page, User, UserProfile
from rango.forms import CategoryForm, PageForm, UserForm, UserProfileForm
from rango.bing_search import run_query
from datetime import datetime

def url_coder(text, encode=True):
	return text.replace(' ', '_') if encode else text.replace('_', ' ')

def get_category_list(max_results=0, starts_with=''):
	clist = []
	if starts_with:
		clist = Category.objects.filter(name__startswith=starts_with)
	else:
		clist = Category.objects.all()
	if max_results > 0:
		if len(clist) > max_results:
			clist = clist[:max_results]

	for category in clist:
		category.url = url_coder(category.name)
	
	return clist

def index(request):
	context               = RequestContext(request)
	top_five_viewed_pages = Page.objects.order_by('-views')[:5]
	context_dict          = {'top_five_views': top_five_viewed_pages}
	context_dict['cat_list'] = get_category_list()

	if request.session.get('last_visit'):
		last_visit_time = request.session.get('last_visit')
		visits = request.session.get('visits', 0)
		if (datetime.now() - datetime.strptime(last_visit_time[:-7], "%Y-%m-%d %H:%M:%S")).days > 0:
			request.session['visits'] = visits + 1
	else:
		request.session['last_visit'] = str(datetime.now())
		request.session['visits'] = 1

	return render_to_response('rango/index.html', context_dict, context)

def about(request):
	context      = RequestContext(request)
	context_dict = {'cat_list': get_category_list()}

	if request.session.get('visits'):
		count = request.session.get('visits')
	else:
		count = 0
	
	context_dict['visits'] = count
	return render_to_response('rango/about.html', context_dict, context)

def category(request, category_name_url):
	context       = RequestContext(request)
	category_name = url_coder(category_name_url, False)
	context_dict  = {'category_name': category_name}
	context_dict['cat_list'] = get_category_list()
	context_dict['category_name_url'] = category_name_url

	try:
		category = Category.objects.get(name=category_name)
		pages    = Page.objects.filter(category=category)
		context_dict['pages']    = pages
		context_dict['category'] = category
	except Category.DoesNotExist:
		pass

	if request.method == 'POST':
		query = request.POST['query'].strip()
		if query:
			result_list = run_query(query)
			context_dict['result_list'] = result_list
	return render_to_response('rango/category.html', context_dict, context)

@login_required
def add_category(request):
	context = RequestContext(request)
	context_dict = {'cat_list': get_category_list()}

	if request.method == 'POST':
		form = CategoryForm(request.POST)
		if form.is_valid():
			form.save(commit=True)
			return index(request)
		else:
			print form.errors
	else:
		form = CategoryForm()
	
	context_dict['form'] = form
	return render_to_response('rango/add_category.html', context_dict, context)

@login_required
def add_page(request, category_name_url):
	context = RequestContext(request)
	context_dict = {'cat_list': get_category_list()}

	category_name = url_coder(category_name_url, encode=False)
	
	if request.method == 'POST':
		form = PageForm(request.POST)
		if form.is_valid():
			page = form.save(commit=False)
			cat = Category.objects.get(name=category_name)
			page.category = cat
			page.views = 0
			page.save()
			return category(request, category_name)
		else:
			print form.errors
	else:
		form = PageForm()

	context_dict['category_name_url'] = category_name_url
	context_dict['category_name'] = category_name
	context_dict['form'] = form

	return render_to_response('rango/add_page.html', context_dict, context)

def register(request):
	context    = RequestContext(request)
	registered = False
	context_dict = {'cat_list': get_category_list()}
	
	if request.method == 'POST':
		user_form    = UserForm(data=request.POST)
		profile_form = UserProfileForm(data=request.POST)
		if user_form.is_valid() and profile_form.is_valid():
			user = user_form.save()
			user.set_password(user.password)
			user.save()
			profile      = profile_form.save(commit=False)
			profile.user = user
			if 'picture' in request.FILES:
				profile.picture = request.FILES['picture']
			profile.save()
			registered = True
		else:
			print user_form.errors, profile_form.errors
	else:
		user_form    = UserForm()
		profile_form = UserProfileForm()
	
	context_dict['user_form'] = user_form
	context_dict['profile_form'] = profile_form
	context_dict['registered'] = registered

	return render_to_response('rango/register.html', context_dict, context)

@login_required
def profile(request):
	context = RequestContext(request)

	context_dict = {'cat_list': get_category_list()}

	u = User.objects.get(username=request.user)

	try:
		up = UserProfile.objects.get(user=u)
	except:
		up = None

	context_dict['user'] = u
	context_dict['userprofile'] = up

	return render_to_response('rango/profile.html', context_dict, context)

def user_login(request):
	context = RequestContext(request)
	context_dict = {'cat_list': get_category_list()}

	if request.method == 'POST':
		username = request.POST['username']
		password = request.POST['password']
		user = authenticate(username=username, password=password)
		if user is not None:
			if user.is_active:
				login(request, user)
				return HttpResponseRedirect('/rango/')
			else:
				return HttpResponse("Your Rango account is disabled.")
		else:
			print "Invalid login details: {0}, {1}".format(username, password)
			if User.objects.filter(username=username):
				return HttpResponse("Password for username " + username + " incorrect.")
			else:
				return HttpResponse("No such user exists.")
	else:
		return render_to_response('rango/login.html', context_dict, context)

@login_required
def restricted(request):
	context = RequestContext(request)
	context_dict = {'cat_list': get_category_list()}
	return render_to_response('rango/restricted.html', context_dict, context)

@login_required
def user_logout(request):
	logout(request)
	return HttpResponseRedirect('/rango/')

def search(request):
    context = RequestContext(request)
    context_dict = {'cat_list': get_category_list()}

    result_list = []

    if request.method == 'POST':
        query = request.POST['query'].strip()

        if query:
            # Run our Bing function to get the results list!
            result_list = run_query(query)

    context_dict['result_list'] = result_list
    return render_to_response('rango/search.html', context_dict, context)

def track_url(request):
	page_id = None
	url = '/rango/'
	if request.method == 'GET':
		if 'page_id' in request.GET:
			page_id = request.GET['page_id']
			try:
				page = Page.objects.get(id=page_id)
				page.views = page.views + 1
				page.save()
				url = page.url
			except:
				pass

	return redirect(url)

@login_required
def like_category(request):
	context = RequestContext(request)
	cat_id = None
	if request.method == 'GET':
		cat_id = request.GET['category_id']

	likes = 0
	if cat_id:
		category = Category.objects.get(id=int(cat_id))
		if category:
			likes = category.likes + 1
			category.likes = likes
			category.save()

	return HttpResponse(likes)

def suggest_category(request):
	context = RequestContext(request)
	
	starts_with = ''
	cat_list = []

	if request.method == 'GET':
		starts_with = request.GET['suggestion']
	else:
		starts_with = request.POST['suggestion']

	cat_list = get_category_list(8, starts_with)
	
	return render_to_response('rango/category_list.html', {'cat_list': cat_list}, context)
